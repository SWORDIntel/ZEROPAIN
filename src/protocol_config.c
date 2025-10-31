# ZeroPain Therapeutics Protocol Configurations
# =============================================
# This file defines various treatment protocols for testing and optimization

# Default Optimized Protocol (Primary)
optimized_protocol:
  name: "ZeroPain Optimized v3.0"
  description: "Primary optimized triple-compound protocol"
  version: "3.0"
  
  compounds:
    sr17018:
      name: "SR-17018"
      role: "Tolerance Protection & Withdrawal Prevention"
      dose_mg: 16.17
      frequency: "BID"  # Twice daily
      administration_times: [0, 12]  # Hours
      
      # Pharmacokinetic parameters
      half_life_hours: 7.0
      bioavailability: 0.7
      volume_distribution_l_kg: 3.0
      clearance_l_h_kg: 0.5
      
      # Pharmacodynamic parameters
      ki_orthosteric_nm: .inf  # No orthosteric binding
      ki_allosteric1_nm: 26.0
      ki_allosteric2_nm: 100.0
      g_protein_bias: 8.2
      beta_arrestin_bias: 0.01
      intrinsic_activity: 0.38
      
      # Special properties
      wash_resistant: true
      prevents_withdrawal: true
      reverses_tolerance: true
      tolerance_rate: 0.0
    
    sr14968:
      name: "SR-14968"
      role: "Sustained G-protein Signaling"
      dose_mg: 25.31
      frequency: "QD"  # Once daily
      administration_times: [0]  # Hours
      
      # Pharmacokinetic parameters
      half_life_hours: 12.0
      bioavailability: 0.6
      volume_distribution_l_kg: 2.5
      clearance_l_h_kg: 0.3
      
      # Pharmacodynamic parameters
      ki_orthosteric_nm: .inf
      ki_allosteric1_nm: 10.0
      ki_allosteric2_nm: 50.0
      g_protein_bias: 10.0  # Highest known G-protein bias
      beta_arrestin_bias: 0.1
      intrinsic_activity: 1.0
      
      # Special properties
      wash_resistant: true
      prevents_withdrawal: false
      reverses_tolerance: false
      tolerance_rate: 0.8
    
    oxycodone:
      name: "Oxycodone"
      role: "Immediate Analgesia"
      dose_mg: 5.07
      frequency: "Q6H"  # Every 6 hours
      administration_times: [0, 6, 12, 18]  # Hours
      
      # Pharmacokinetic parameters
      half_life_hours: 3.5
      bioavailability: 0.8
      volume_distribution_l_kg: 2.6
      clearance_l_h_kg: 0.8
      
      # Pharmacodynamic parameters
      ki_orthosteric_nm: 18.0
      ki_allosteric1_nm: .inf
      ki_allosteric2_nm: .inf
      g_protein_bias: 1.0
      beta_arrestin_bias: 1.0
      intrinsic_activity: 0.8
      
      # Special properties
      wash_resistant: false
      prevents_withdrawal: false
      reverses_tolerance: false
      tolerance_rate: 1.0

  # Clinical targets
  targets:
    treatment_success_rate: ">70%"
    tolerance_development: "<5%"
    addiction_signs: "<3%"
    withdrawal_symptoms: "0%"
    therapeutic_window: ">15x"
    mean_pain_reduction: ">50%"
    cost_per_qaly: "<$30,000"

  # Simulation parameters
  simulation:
    duration_days: 90
    n_patients: 100000
    random_seed: 42
    cpu_cores: 22

# Alternative Protocol 1: High-Dose SR-17018
high_dose_sr17018:
  name: "High-Dose SR-17018 Protocol"
  description: "Emphasis on tolerance protection with higher SR-17018 dose"
  
  compounds:
    sr17018:
      dose_mg: 32.0  # Double dose
      frequency: "BID"
      administration_times: [0, 12]
    sr14968:
      dose_mg: 15.0  # Reduced dose
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 7.5   # Increased for immediate effect
      frequency: "Q6H"
      administration_times: [0, 6, 12, 18]

# Alternative Protocol 2: SR-17018 Monotherapy Plus
sr17018_plus_protocol:
  name: "SR-17018 Plus Protocol"
  description: "Dual compound protocol without SR-14968"
  
  compounds:
    sr17018:
      dose_mg: 48.0  # Higher monotherapy dose
      frequency: "BID"
      administration_times: [0, 12]
    oxycodone:
      dose_mg: 10.0  # Standard dose
      frequency: "Q4H"  # More frequent
      administration_times: [0, 4, 8, 12, 16, 20]

# Alternative Protocol 3: Extended Release
extended_release_protocol:
  name: "Extended Release Protocol"
  description: "Longer-acting formulations for improved compliance"
  
  compounds:
    sr17018:
      dose_mg: 24.0
      frequency: "QD"  # Once daily extended release
      administration_times: [0]
      formulation: "extended_release"
    sr14968:
      dose_mg: 50.0  # Higher dose for QD
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 15.0
      frequency: "BID"  # Extended release oxycodone
      administration_times: [0, 12]
      formulation: "extended_release"

# Alternative Protocol 4: Low-Risk Population
low_risk_protocol:
  name: "Low-Risk Population Protocol"
  description: "Optimized for patients with low addiction risk"
  
  compounds:
    sr17018:
      dose_mg: 12.0   # Lower protective dose
      frequency: "BID"
      administration_times: [0, 12]
    sr14968:
      dose_mg: 20.0   # Standard dose
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 7.5    # Higher analgesic dose
      frequency: "Q6H"
      administration_times: [0, 6, 12, 18]

# Alternative Protocol 5: High-Risk Population
high_risk_protocol:
  name: "High-Risk Population Protocol"
  description: "Maximum protection for addiction-prone patients"
  
  compounds:
    sr17018:
      dose_mg: 40.0   # Maximum protective dose
      frequency: "BID"
      administration_times: [0, 12]
    sr14968:
      dose_mg: 35.0   # Higher G-protein bias
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 3.0    # Minimal traditional opioid
      frequency: "Q8H"  # Less frequent
      administration_times: [0, 8, 16]

# Alternative Protocol 6: Rapid Titration
rapid_titration_protocol:
  name: "Rapid Titration Protocol"
  description: "Fast dose escalation for severe pain"
  
  week_1:
    sr17018: {dose_mg: 8.0, frequency: "BID"}
    sr14968: {dose_mg: 12.5, frequency: "QD"}
    oxycodone: {dose_mg: 2.5, frequency: "Q6H"}
  
  week_2:
    sr17018: {dose_mg: 16.0, frequency: "BID"}
    sr14968: {dose_mg: 25.0, frequency: "QD"}
    oxycodone: {dose_mg: 5.0, frequency: "Q6H"}
  
  maintenance:
    sr17018: {dose_mg: 24.0, frequency: "BID"}
    sr14968: {dose_mg: 37.5, frequency: "QD"}
    oxycodone: {dose_mg: 7.5, frequency: "Q6H"}

# Alternative Protocol 7: Elderly Population
elderly_protocol:
  name: "Elderly Population Protocol"
  description: "Adjusted for reduced clearance and increased sensitivity"
  
  compounds:
    sr17018:
      dose_mg: 10.0   # Reduced for slower clearance
      frequency: "BID"
      administration_times: [0, 12]
    sr14968:
      dose_mg: 15.0   # Reduced initial dose
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 2.5    # Much lower starting dose
      frequency: "Q8H"  # Less frequent
      administration_times: [0, 8, 16]
  
  # Special considerations
  monitoring:
    renal_function: "required"
    cognitive_assessment: "weekly"
    fall_risk: "high_priority"

# Alternative Protocol 8: Cancer Pain
cancer_pain_protocol:
  name: "Cancer Pain Protocol"
  description: "Higher doses for severe cancer-related pain"
  
  compounds:
    sr17018:
      dose_mg: 20.0   # Higher protective dose
      frequency: "BID"
      administration_times: [0, 12]
    sr14968:
      dose_mg: 40.0   # Maximum sustained signaling
      frequency: "QD"
      administration_times: [0]
    oxycodone:
      dose_mg: 10.0   # Higher analgesic dose
      frequency: "Q4H"  # More frequent for breakthrough
      administration_times: [0, 4, 8, 12, 16, 20]
  
  # Breakthrough medication
  breakthrough:
    compound: "oxycodone"
    dose_mg: 2.5
    max_doses_per_day: 4

# Quality Assurance Parameters
quality_parameters:
  manufacturing:
    purity: ">99.5%"
    stability: "24_months"
    shelf_life: "36_months"
  
  clinical:
    bioequivalence: "FDA_approved"
    dissolution: "USP_standards"
    content_uniformity: "Â±5%"

# Economic Parameters
economic_parameters:
  cost_per_day:
    sr17018: 15.00  # USD
    sr14968: 22.00  # USD
    oxycodone: 3.00  # USD
    total_daily: 40.00  # USD
  
  qaly_parameters:
    utility_gain_factor: 0.25
    discount_rate: 0.03
    time_horizon_years: 5
    
  cost_effectiveness:
    target_cost_per_qaly: 30000  # USD
    comparator: "morphine_equivalent"
    comparator_cost_per_qaly: 50000  # USD

# Clinical Trial Parameters
clinical_trial_parameters:
  phase_1:
    n_subjects: 30
    duration_days: 14
    primary_endpoint: "safety_pharmacokinetics"
  
  phase_2:
    n_subjects: 200
    duration_days: 84
    primary_endpoint: "efficacy_dose_response"
    
  phase_3:
    n_subjects: 1200
    duration_days: 365
    primary_endpoint: "non_inferiority_morphine"

# Regulatory Information
regulatory:
  fda_status: "pre_clinical"
  ema_status: "pre_clinical"
  orphan_designation: false
  fast_track_designation: true
  breakthrough_therapy: true