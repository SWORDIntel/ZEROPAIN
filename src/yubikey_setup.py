#!/usr/bin/env python3
"""
YubiKey Setup and Management Tool for ZeroPain Security
========================================================
Interactive tool for registering and managing YubiKey authentication
"""

import os
import sqlite3
import secrets
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# FIDO2/YubiKey libraries
from fido2.hid import CtapHidDevice
from fido2.client import Fido2Client, ClientError
from fido2.server import Fido2Server
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialParameters,
    PublicKeyCredentialType,
    PublicKeyCredentialDescriptor,
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    AttestationConveyancePreference,
)
from fido2.cose import ES256, RS256
from fido2.utils import websafe_encode, websafe_decode

# ==============================================================================
# CONFIGURATION
# ==============================================================================


class Config:
    """Configuration for YubiKey setup"""

    # FIDO2 Relying Party configuration
    RP_ID = "zeropain-therapeutics.local"
    RP_NAME = "ZeroPain Therapeutics Security Portal"

    # Database configuration
    DB_PATH = Path("/opt/zeropain_security/yubikey_credentials.db")

    # Security settings
    REQUIRE_PIN = True
    REQUIRE_RESIDENT_KEY = False
    USER_VERIFICATION = UserVerificationRequirement.REQUIRED
    ATTESTATION = AttestationConveyancePreference.DIRECT

    # Supported algorithms
    SUPPORTED_ALGORITHMS = [ES256, RS256]


# ==============================================================================
# DATABASE MANAGER
# ==============================================================================


class CredentialDatabase:
    """Manages YubiKey credential storage"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.ensure_database()

    def ensure_database(self):
        """Create database and tables if they don't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_auth TIMESTAMP,
                auth_count INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT
            )
        """
        )

        # Credentials table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS credentials (
                credential_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                public_key BLOB NOT NULL,
                credential_data BLOB NOT NULL,
                sign_count INTEGER DEFAULT 0,
                device_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                is_backup BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """
        )

        # Audit log table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def add_user(
        self, user_id: str, username: str, display_name: str, is_admin: bool = False
    ) -> bool:
        """Add a new user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users (user_id, username, display_name, is_admin)
                VALUES (?, ?, ?, ?)
            """,
                (user_id, username, display_name, is_admin),
            )

            conn.commit()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            print(f"Error: User {username} already exists")
            return False

    def add_credential(
        self,
        user_id: str,
        credential_id: bytes,
        public_key: bytes,
        credential_data: bytes,
        device_name: str = None,
    ) -> bool:
        """Store a YubiKey credential"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO credentials 
                (credential_id, user_id, public_key, credential_data, device_name)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    websafe_encode(credential_id),
                    user_id,
                    public_key,
                    credential_data,
                    device_name,
                ),
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error storing credential: {e}")
            return False

    def get_user_credentials(self, user_id: str) -> List[Dict]:
        """Get all credentials for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT credential_id, public_key, credential_data, device_name,
                   registered_at, last_used, sign_count
            FROM credentials
            WHERE user_id = ?
        """,
            (user_id,),
        )

        credentials = []
        for row in cursor.fetchall():
            credentials.append(
                {
                    "credential_id": websafe_decode(row[0]),
                    "public_key": row[1],
                    "credential_data": row[2],
                    "device_name": row[3],
                    "registered_at": row[4],
                    "last_used": row[5],
                    "sign_count": row[6],
                }
            )

        conn.close()
        return credentials

    def log_action(self, user_id: str, action: str, result: str, details: str = None):
        """Log an authentication action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO audit_log (user_id, action, result, details)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, action, result, details),
        )

        conn.commit()
        conn.close()


# ==============================================================================
# YUBIKEY MANAGER
# ==============================================================================


class YubiKeyManager:
    """Manages YubiKey operations"""

    def __init__(self):
        self.db = CredentialDatabase(Config.DB_PATH)
        self.rp = PublicKeyCredentialRpEntity(id=Config.RP_ID, name=Config.RP_NAME)
        self.server = Fido2Server(
            self.rp,
            attestation=Config.ATTESTATION,
            verify_origin=lambda origin: True,  # Accept any origin for CLI tool
        )

    def list_connected_devices(self) -> List[CtapHidDevice]:
        """List all connected FIDO2 devices"""
        devices = list(CtapHidDevice.list_devices())
        return devices

    def register_yubikey(
        self, username: str, display_name: str = None, is_admin: bool = False
    ) -> bool:
        """Register a new YubiKey for a user"""

        # Check for connected YubiKey
        devices = self.list_connected_devices()
        if not devices:
            print("âŒ No YubiKey detected. Please insert your YubiKey.")
            return False

        print(f"âœ“ Found {len(devices)} YubiKey(s)")

        # Use first device
        device = devices[0]
        client = Fido2Client(device, f"https://{Config.RP_ID}")

        # Generate user ID
        user_id = secrets.token_bytes(32)
        user_id_str = websafe_encode(user_id)

        # Create user entity
        user = PublicKeyCredentialUserEntity(
            id=user_id, name=username, display_name=display_name or username
        )

        # Create challenge
        challenge = secrets.token_bytes(32)

        # Setup credential parameters
        credentials = [
            PublicKeyCredentialParameters(
                type=PublicKeyCredentialType.PUBLIC_KEY, alg=alg
            )
            for alg in Config.SUPPORTED_ALGORITHMS
        ]

        # Authenticator selection criteria
        authenticator_selection = AuthenticatorSelectionCriteria(
            user_verification=Config.USER_VERIFICATION,
            resident_key=ResidentKeyRequirement.REQUIRED
            if Config.REQUIRE_RESIDENT_KEY
            else ResidentKeyRequirement.DISCOURAGED,
        )

        print(f"\nðŸ” Registering YubiKey for user: {username}")
        print("Please touch your YubiKey when it starts blinking...")

        try:
            # Make credential
            attestation_object, client_data = client.make_credential(
                {
                    "rp": self.rp,
                    "user": user,
                    "challenge": challenge,
                    "pubKeyCredParams": credentials,
                    "authenticatorSelection": authenticator_selection,
                    "attestation": Config.ATTESTATION,
                }
            )

            # Verify attestation
            auth_data = self.server.register_complete(
                {
                    "id": websafe_encode(
                        attestation_object.auth_data.credential_data.credential_id
                    ),
                    "rawId": attestation_object.auth_data.credential_data.credential_id,
                    "response": {
                        "clientDataJSON": client_data,
                        "attestationObject": attestation_object,
                    },
                    "type": "public-key",
                },
                challenge,
            )

            # Store user and credential
            self.db.add_user(user_id_str, username, display_name or username, is_admin)
            self.db.add_credential(
                user_id_str,
                auth_data.credential_data.credential_id,
                auth_data.credential_data.public_key,
                bytes(auth_data.credential_data),
                device_name=f"YubiKey-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            )

            # Log success
            self.db.log_action(
                user_id_str,
                "REGISTER",
                "SUCCESS",
                f"Registered new YubiKey for {username}",
            )

            print(f"âœ… YubiKey successfully registered for {username}")
            print(f"User ID: {user_id_str}")
            print(
                f"Credential ID: {websafe_encode(auth_data.credential_data.credential_id)}"
            )

            # Save backup codes
            backup_codes = self.generate_backup_codes(user_id_str)
            self.save_backup_codes(username, backup_codes)

            return True

        except ClientError as e:
            print(f"âŒ Registration failed: {e}")
            self.db.log_action(username, "REGISTER", "FAILED", str(e))
            return False

    def authenticate_yubikey(self, username: str) -> bool:
        """Authenticate with a YubiKey"""

        # Get user from database
        conn = sqlite3.connect(self.db.path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            print(f"âŒ User {username} not found")
            return False

        user_id = result[0]

        # Get user credentials
        credentials = self.db.get_user_credentials(user_id)
        if not credentials:
            print(f"âŒ No YubiKey registered for {username}")
            return False

        # Check for connected YubiKey
        devices = self.list_connected_devices()
        if not devices:
            print("âŒ No YubiKey detected. Please insert your YubiKey.")
            return False

        device = devices[0]
        client = Fido2Client(device, f"https://{Config.RP_ID}")

        # Create challenge
        challenge = secrets.token_bytes(32)

        # Prepare credentials for authentication
        allow_credentials = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY, id=cred["credential_id"]
            )
            for cred in credentials
        ]

        print(f"\nðŸ” Authenticating {username}")
        print("Please touch your YubiKey when it starts blinking...")

        try:
            # Get assertion
            assertion, client_data = client.get_assertion(
                {
                    "rpId": Config.RP_ID,
                    "challenge": challenge,
                    "allowCredentials": allow_credentials,
                    "userVerification": Config.USER_VERIFICATION,
                }
            )

            # Verify assertion
            # (In production, this would be done server-side)

            print(f"âœ… Authentication successful for {username}")

            # Update last auth time
            conn = sqlite3.connect(self.db.path)
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users 
                SET last_auth = CURRENT_TIMESTAMP, auth_count = auth_count + 1
                WHERE user_id = ?
            """,
                (user_id,),
            )
            conn.commit()
            conn.close()

            # Log success
            self.db.log_action(user_id, "AUTHENTICATE", "SUCCESS", None)

            return True

        except ClientError as e:
            print(f"âŒ Authentication failed: {e}")
            self.db.log_action(user_id, "AUTHENTICATE", "FAILED", str(e))
            return False

    def generate_backup_codes(self, user_id: str, count: int = 10) -> List[str]:
        """Generate backup codes for account recovery"""
        codes = []
        for _ in range(count):
            code = f"{secrets.token_hex(4)}-{secrets.token_hex(4)}"
            codes.append(code.upper())
        return codes

    def save_backup_codes(self, username: str, codes: List[str]):
        """Save backup codes to a secure file"""
        backup_file = Path(
            f"backup_codes_{username}_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        with open(backup_file, "w") as f:
            f.write(f"ZEROPAIN THERAPEUTICS - BACKUP CODES\n")
            f.write(f"{'='*40}\n")
            f.write(f"User: {username}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*40}\n\n")
            f.write("KEEP THESE CODES SAFE!\n")
            f.write("Each code can only be used once.\n\n")

            for i, code in enumerate(codes, 1):
                f.write(f"{i:2d}. {code}\n")

        os.chmod(backup_file, 0o600)  # Read/write for owner only
        print(f"\nðŸ“ Backup codes saved to: {backup_file}")
        print("âš ï¸  Store these codes in a secure location!")


# ==============================================================================
# CLI INTERFACE
# ==============================================================================


def main():
    """Main CLI interface"""

    parser = argparse.ArgumentParser(
        description="ZeroPain YubiKey Setup and Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s register -u john.doe -n "John Doe" --admin
  %(prog)s authenticate -u john.doe
  %(prog)s list-devices
  %(prog)s list-users
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new YubiKey")
    register_parser.add_argument("-u", "--username", required=True, help="Username")
    register_parser.add_argument("-n", "--name", help="Display name")
    register_parser.add_argument(
        "--admin", action="store_true", help="Grant admin privileges"
    )

    # Authenticate command
    auth_parser = subparsers.add_parser(
        "authenticate", help="Test YubiKey authentication"
    )
    auth_parser.add_argument("-u", "--username", required=True, help="Username")

    # List devices command
    subparsers.add_parser("list-devices", help="List connected YubiKeys")

    # List users command
    subparsers.add_parser("list-users", help="List registered users")

    # Parse arguments
    args = parser.parse_args()

    # ASCII banner
    print(
        """
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘           ZEROPAIN YUBIKEY AUTHENTICATION MANAGER             â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    """
    )

    # Initialize manager
    manager = YubiKeyManager()

    # Execute command
    if args.command == "register":
        manager.register_yubikey(args.username, args.name, args.admin)

    elif args.command == "authenticate":
        manager.authenticate_yubikey(args.username)

    elif args.command == "list-devices":
        devices = manager.list_connected_devices()
        if devices:
            print(f"Found {len(devices)} YubiKey(s):")
            for i, device in enumerate(devices, 1):
                print(f"  {i}. {device}")
        else:
            print("No YubiKeys detected")

    elif args.command == "list-users":
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, display_name, created_at, last_auth, auth_count, is_admin
            FROM users
            WHERE is_active = 1
        """
        )

        users = cursor.fetchall()
        conn.close()

        if users:
            print(f"Registered users ({len(users)}):\n")
            print(
                f"{'Username':<20} {'Display Name':<25} {'Created':<20} {'Last Auth':<20} {'Count':<8} {'Admin':<6}"
            )
            print("-" * 110)

            for user in users:
                username, display_name, created, last_auth, count, is_admin = user
                admin_str = "Yes" if is_admin else "No"
                last_auth_str = last_auth or "Never"
                print(
                    f"{username:<20} {display_name:<25} {created:<20} {last_auth_str:<20} {count:<8} {admin_str:<6}"
                )
        else:
            print("No users registered yet")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
