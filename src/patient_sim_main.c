/*
 * patient_sim.c - Main simulation implementation
 * 100,000 Patient Monte Carlo Simulation
 * SR-17018 + SR-14968 + DPP-26 Protocol
 * 
 * Compile with native optimizations:
 * gcc -O3 -march=native -mtune=native -fopenmp patient_sim.c compound_profiles.c statistics.c -lm -o patient_sim
 * 
 * Run: ./patient_sim
 * Thread control: OMP_NUM_THREADS=22 ./patient_sim
 */

#include "patient_sim.h"
#include <float.h>
#include <limits.h>

// ============================================================================
// GLOBAL STATE
// ============================================================================

// Thread-local RNG state for parallel execution
static __thread uint64_t rng_state = 0;
static __thread int rng_initialized = 0;

// Progress tracking
static int processed_patients = 0;
static omp_lock_t progress_lock;

// ============================================================================
// RANDOM NUMBER GENERATION
// ============================================================================

uint64_t xorshift64(void) {
    if (!rng_initialized) {
        // Initialize with thread ID and time
        rng_state = (uint64_t)time(NULL) ^ (uint64_t)omp_get_thread_num() ^ 0x123456789ABCDEF0;
        rng_initialized = 1;
    }
    
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 7;
    rng_state ^= rng_state << 17;
    return rng_state;
}

float random_uniform(void) {
    return xorshift64() / (float)UINT64_MAX;
}

float random_normal(float mean, float stddev) {
    static __thread int has_spare = 0;
    static __thread float spare;
    
    if (has_spare) {
        has_spare = 0;
        return spare * stddev + mean;
    }
    
    has_spare = 1;
    float u = random_uniform();
    float v = random_uniform();
    float mag = stddev * sqrtf(-2.0f * logf(u + FLT_MIN));
    spare = mag * cosf(2.0f * M_PI * v);
    return mag * sinf(2.0f * M_PI * v) + mean;
}

int random_categorical(const float* probs, int n) {
    float r = random_uniform();
    float cumsum = 0;
    for (int i = 0; i < n; i++) {
        cumsum += probs[i];
        if (r <= cumsum) return i;
    }
    return n - 1;
}

// ============================================================================
// POPULATION GENERATION
// ============================================================================

PatientCharacteristics* generate_population(int n) {
    PatientCharacteristics* patients = (PatientCharacteristics*)calloc(n, sizeof(PatientCharacteristics));
    if (!patients) {
        fprintf(stderr, "Failed to allocate memory for %d patients\n", n);
        exit(1);
    }
    
    // Distribution parameters
    const float pain_type_probs[] = {0.2, 0.3, 0.15, 0.2, 0.15};  // 5 pain types
    const float risk_probs[] = {0.4, 0.35, 0.2, 0.05};  // 4 risk categories
    const float genetic_probs[] = {0.7, 0.1, 0.15, 0.05};  // 4 metabolizer types
    
    #pragma omp parallel for
    for (int i = 0; i < n; i++) {
        PatientCharacteristics* p = &patients[i];
        
        // Demographics
        p->patient_id = i;
        p->age = 18 + (uint8_t)(random_uniform() * 62);  // 18-80 years
        p->sex = random_uniform() < 0.52 ? 1 : 0;  // 52% female
        p->weight = clamp(50 + random_normal(25, 15), 40, 150);  // kg
        p->bmi = clamp(18.5 + random_normal(6, 4), 16, 45);
        
        // Pain characteristics
        p->pain_type = random_categorical(pain_type_probs, 5);
        p->baseline_pain_score = clamp(4 + random_normal(2.5, 1.5), 1, 10);
        p->pain_duration_months = 1 + (uint16_t)(random_uniform() * 120);  // 1-120 months
        
        // Prior opioid use (30% have prior use)
        p->prior_opioid_use = random_uniform() < 0.3;
        p->prior_opioid_dose_mme = p->prior_opioid_use ? random_uniform() * 90 : 0;
        
        // Risk factors
        p->risk_category = random_categorical(risk_probs, 4);
        p->addiction_history = random_uniform() < 0.1;  // 10%
        p->mental_health_comorbidity = random_uniform() < 0.25;  // 25%
        p->respiratory_disease = random_uniform() < 0.12;  // 12%
        
        // Organ function
        p->renal_function = clamp(90 + random_normal(0, 20), 15, 120);  // eGFR
        p->hepatic_function = clamp(1.0 - (p->age > 60 ? 0.1 : 0) + random_normal(0, 0.1), 0.3, 1.0);
        
        // Genetics
        p->cyp2d6_phenotype = random_categorical(genetic_probs, 4);
        p->cyp3a4_phenotype = random_categorical(genetic_probs, 4);
        p->oprm1_variant = random_uniform() < 0.15;  // 15% prevalence
        p->comt_variant = random_uniform() < 0.25;  // 25% prevalence
        
        // Adherence (higher for cancer patients)
        if (p->pain_type == CHRONIC_CANCER) {
            p->adherence_probability = clamp(0.85 + random_normal(0, 0.1), 0.5, 1.0);
        } else {
            p->adherence_probability = clamp(0.7 + random_normal(0, 0.15), 0.3, 0.95);
        }
    }
    
    return patients;
}

void free_population(PatientCharacteristics* patients) {
    free(patients);
}

// ============================================================================
// PHARMACOKINETIC MODELING
// ============================================================================

float calculate_clearance_factor(const PatientCharacteristics* p) {
    float cl_factor = 1.0;
    
    // Age adjustment
    if (p->age > 65) {
        cl_factor *= (1.0 - 0.01 * (p->age - 65));  // 1% reduction per year over 65
    }
    
    // Renal function
    cl_factor *= p->renal_function / 90.0;
    
    // Hepatic function
    cl_factor *= p->hepatic_function;
    
    // Genetic factors
    switch (p->cyp2d6_phenotype) {
        case POOR_METABOLIZER:
            cl_factor *= 0.3;
            break;
        case RAPID_METABOLIZER:
            cl_factor *= 1.5;
            break;
        case ULTRA_RAPID_METABOLIZER:
            cl_factor *= 2.0;
            break;
        default:
            break;
    }
    
    // Weight adjustment
    cl_factor *= powf(p->weight / 70.0, 0.75);  // Allometric scaling
    
    return clamp(cl_factor, 0.2, 3.0);
}

float calculate_concentration(float dose, float t_half, float bioavail, 
                             float cl_factor, float time_since_dose) {
    // One-compartment model with first-order elimination
    float ke = 0.693 / (t_half / cl_factor);  // Adjusted elimination constant
    float ka = 2.0;  // Absorption rate constant (1/h)
    
    // Cmax occurs at tmax = ln(ka/ke)/(ka-ke)
    float concentration;
    if (bioavail < 1.0) {
        // Oral administration
        concentration = dose * bioavail * ka / (ka - ke) * 
                       (expf(-ke * time_since_dose) - expf(-ka * time_since_dose));
    } else {
        // IV administration
        concentration = dose * expf(-ke * time_since_dose);
    }
    
    return fmaxf(concentration, 0);
}

// ============================================================================
// RECEPTOR DYNAMICS
// ============================================================================

typedef struct {
    float mu_receptor_activity;
    float tolerance_level;
    float beta_arrestin_signal;
} ReceptorState;

ReceptorState calculate_receptor_dynamics(float sr17018_conc, float sr14968_conc, 
                                          float dpp26_conc, float tolerance_prev) {
    ReceptorState state = {0};
    
    // SR-17018: Allosteric modulator, prevents tolerance
    float sr17018_binding = sr17018_conc / (SR17018.ki_allosteric1 + sr17018_conc);
    float sr17018_effect = sr17018_binding * SR17018.intrinsic_activity * SR17018.g_protein_bias;
    
    // SR-14968: High G-protein bias
    float sr14968_binding = sr14968_conc / (SR14968.ki_allosteric1 + sr14968_conc);
    float sr14968_effect = sr14968_binding * SR14968.intrinsic_activity * SR14968.g_protein_bias;
    
    // DPP-26: Orthosteric agonist
    float dpp26_binding = dpp26_conc / (DPP26.ki_orthosteric + dpp26_conc);
    float dpp26_effect = dpp26_binding * DPP26.intrinsic_activity;
    
    // Competitive inhibition between SR compounds
    if (sr17018_binding > 0 && sr14968_binding > 0) {
        float competition = sr17018_conc / (sr17018_conc + sr14968_conc * 10);
        sr14968_effect *= (1 - 0.3 * competition);
    }
    
    // Total receptor activation
    state.mu_receptor_activity = sr17018_effect + sr14968_effect + dpp26_effect;
    
    // Apply tolerance
    state.mu_receptor_activity /= (1 + tolerance_prev);
    
    // Î²-arrestin signaling (leads to tolerance/addiction)
    state.beta_arrestin_signal = dpp26_binding * DPP26.beta_arrestin_bias + 
                                 sr14968_binding * SR14968.beta_arrestin_bias * 0.1;
    
    // Tolerance development
    float tolerance_rate = DPP26.tolerance_rate * dpp26_binding;
    
    // SR-17018 reverses tolerance
    if (sr17018_binding > 0.3) {
        tolerance_rate -= sr17018_binding * 0.02;  // Reversal rate
    }
    
    state.tolerance_level = tolerance_prev + tolerance_rate * 0.01;  // Per timestep
    state.tolerance_level = fmaxf(0, state.tolerance_level);  // Can't go negative
    
    return state;
}

// ============================================================================
// TREATMENT SIMULATION
// ============================================================================

TreatmentOutcome simulate_patient_treatment(const PatientCharacteristics* p, 
                                           const Protocol* protocol) {
    TreatmentOutcome outcome = {0};
    outcome.patient_id = p->patient_id;
    
    // Calculate dosing adjustments
    float cl_factor = calculate_clearance_factor(p);
    
    // Adjust doses for patient factors
    float sr17018_dose = protocol->sr17018_dose;
    float sr14968_dose = protocol->sr14968_dose;
    float dpp26_dose = protocol->dpp26_dose;
    
    // Dose reduction for elderly or impaired
    if (p->age > 70 || p->renal_function < 30) {
        dpp26_dose *= 0.75;
    }
    
    // Simulation state
    float tolerance = 0;
    float cumulative_analgesia = 0;
    int adverse_events = 0;
    float max_beta_arrestin = 0;
    float total_cost = 0;
    
    // Time tracking
    int timesteps_per_day = TIMESTEPS_PER_DAY;
    float dt = 24.0 / timesteps_per_day;  // hours per timestep
    
    // Dosing schedules (hours since last dose)
    float time_since_sr17018 = 0;
    float time_since_sr14968 = 0;
    float time_since_dpp26 = 0;
    
    // Main simulation loop
    for (int day = 0; day < SIMULATION_DAYS; day++) {
        float daily_pain_sum = 0;
        float daily_analgesia_sum = 0;
        
        for (int ts = 0; ts < timesteps_per_day; ts++) {
            float hour = day * 24.0 + ts * dt;
            
            // Check dosing schedule
            if (fmodf(hour, 12.0) < dt) {  // BID for SR-17018
                time_since_sr17018 = 0;
            }
            if (fmodf(hour, 24.0) < dt) {  // QD for SR-14968
                time_since_sr14968 = 0;
            }
            if (fmodf(hour, 6.0) < dt) {  // Q6H for DPP-26
                time_since_dpp26 = 0;
            }
            
            // Calculate concentrations
            float sr17018_conc = calculate_concentration(sr17018_dose, SR17018.t_half, 
                                                        SR17018.bioavailability, cl_factor, 
                                                        time_since_sr17018);
            float sr14968_conc = calculate_concentration(sr14968_dose, SR14968.t_half,
                                                        SR14968.bioavailability, cl_factor,
                                                        time_since_sr14968);
            float dpp26_conc = calculate_concentration(dpp26_dose, DPP26.t_half,
                                                      DPP26.bioavailability, cl_factor,
                                                      time_since_dpp26);
            
            // Update receptor dynamics
            ReceptorState receptor = calculate_receptor_dynamics(sr17018_conc, sr14968_conc,
                                                                dpp26_conc, tolerance);
            tolerance = receptor.tolerance_level;
            max_beta_arrestin = fmaxf(max_beta_arrestin, receptor.beta_arrestin_signal);
            
            // Calculate analgesia
            float analgesia = receptor.mu_receptor_activity;
            
            // Genetic modulation
            if (p->oprm1_variant) analgesia *= 0.8;
            if (p->comt_variant) analgesia *= 1.1;
            
            // Calculate pain score
            float pain = p->baseline_pain_score * (1 - analgesia * 0.7);
            pain = clamp(pain, 0, 10);
            
            daily_pain_sum += pain;
            daily_analgesia_sum += analgesia;
            cumulative_analgesia += analgesia;
            
            // Check for adverse events
            if (random_uniform() < 0.001 * receptor.beta_arrestin_signal) {
                adverse_events++;
            }
            
            // Update time
            time_since_sr17018 += dt;
            time_since_sr14968 += dt;
            time_since_dpp26 += dt;
        }
        
        // Record daily averages
        outcome.daily_pain_scores[day] = daily_pain_sum / timesteps_per_day;
        outcome.analgesia_achieved[day] = daily_analgesia_sum / timesteps_per_day;
        
        // Add daily cost
        total_cost += COST_PER_DAY_DPP26;
        
        // Check for treatment failure
        if (outcome.daily_pain_scores[day] > PAIN_CONTROL_FAILURE) {
            outcome.treatment_success = false;
            outcome.discontinuation_day = day;
            strcpy(outcome.discontinuation_reason, "inadequate_analgesia");
            break;
        }
        
        // Check adherence
        if (random_uniform() > p->adherence_probability) {
            outcome.treatment_success = false;
            outcome.discontinuation_day = day;
            strcpy(outcome.discontinuation_reason, "non_adherence");
            break;
        }
        
        // Trial period evaluation
        if (day == TRIAL_PERIOD_DAYS) {
            float avg_pain = 0;
            for (int i = 0; i < TRIAL_PERIOD_DAYS; i++) {
                avg_pain += outcome.daily_pain_scores[i];
            }
            avg_pain /= TRIAL_PERIOD_DAYS;
            
            if (avg_pain > 5.0) {
                outcome.treatment_success = false;
                outcome.discontinuation_day = day;
                strcpy(outcome.discontinuation_reason, "trial_failure");
                break;
            }
        }
    }
    
    // Calculate final outcomes
    outcome.avg_pain_reduction = cumulative_analgesia / (SIMULATION_DAYS * timesteps_per_day);
    outcome.tolerance_developed = tolerance > TOLERANCE_THRESHOLD;
    outcome.addiction_signs = max_beta_arrestin > ADDICTION_RISK_THRESHOLD / 100.0;
    outcome.withdrawal_occurred = false;  // SR-17018 prevents withdrawal
    outcome.adverse_event_count = adverse_events;
    outcome.final_tolerance_level = tolerance;
    outcome.total_cost = total_cost;
    
    // QALY calculation
    float qaly_days = outcome.discontinuation_day > 0 ? outcome.discontinuation_day : SIMULATION_DAYS;
    outcome.qaly_gained = (qaly_days / DAYS_PER_YEAR) * QALY_UTILITY_GAIN_FACTOR * outcome.avg_pain_reduction;
    
    // Success determination
    if (outcome.discontinuation_day == 0) {
        outcome.treatment_success = true;
        outcome.discontinuation_day = SIMULATION_DAYS;
    }
    
    return outcome;
}

// ============================================================================
// PARALLEL SIMULATION
// ============================================================================

void simulate_population_parallel(const PatientCharacteristics* patients,
                                 const Protocol* protocol,
                                 TreatmentOutcome* outcomes,
                                 int n_patients) {
    processed_patients = 0;
    
    #pragma omp parallel for schedule(dynamic, BATCH_SIZE)
    for (int i = 0; i < n_patients; i++) {
        outcomes[i] = simulate_patient_treatment(&patients[i], protocol);
        
        // Update progress
        #pragma omp critical
        {
            processed_patients++;
            if (processed_patients % 1000 == 0) {
                printf("\rProgress: %d/%d patients (%.1f%%)", 
                       processed_patients, n_patients, 
                       100.0 * processed_patients / n_patients);
                fflush(stdout);
            }
        }
    }
    printf("\rProgress: %d/%d patients (100.0%%)\n", n_patients, n_patients);
}

// ============================================================================
// MAIN ENTRY POINT
// ============================================================================

int main(int argc, char** argv) {
    // Print header
    printf("\n");
    printf("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\n");
    printf("â•‘          ZEROPAIN THERAPEUTICS - 100K PATIENT SIMULATION      â•‘\n");
    printf("â•‘                  SR-17018 + SR-14968 + DPP-26                 â•‘\n");
    printf("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\n");
    printf("\n");
    
    // System info
    int max_threads = omp_get_max_threads();
    printf("System Configuration:\n");
    printf("  Max threads available: %d\n", max_threads);
    printf("  Threads to use: %d\n", max_threads > MAX_THREADS ? MAX_THREADS : max_threads);
    printf("  Patient population: %d\n", N_PATIENTS);
    printf("  Simulation duration: %d days\n", SIMULATION_DAYS);
    printf("\n");
    
    // Set thread count
    omp_set_num_threads(max_threads > MAX_THREADS ? MAX_THREADS : max_threads);
    omp_init_lock(&progress_lock);
    
    // Initialize protocol
    Protocol protocol = {
        .sr17018_dose = 16.17f,  // mg BID
        .sr14968_dose = 25.31f,  // mg QD
        .dpp26_dose = 5.07f      // mg Q6H (replacing oxycodone)
    };
    
    printf("Protocol Configuration:\n");
    printf("  SR-17018: %.2f mg BID (tolerance protector)\n", protocol.sr17018_dose);
    printf("  SR-14968: %.2f mg QD (sustained signaling)\n", protocol.sr14968_dose);
    printf("  DPP-26:   %.2f mg Q6H (safer opioid alternative)\n", protocol.dpp26_dose);
    printf("\n");
    
    // Generate patient population
    printf("Phase 1: Generating patient population...\n");
    double start_time = omp_get_wtime();
    PatientCharacteristics* patients = generate_population(N_PATIENTS);
    double gen_time = omp_get_wtime() - start_time;
    printf("  Population generated in %.2f seconds\n\n", gen_time);
    
    // Allocate outcomes
    TreatmentOutcome* outcomes = (TreatmentOutcome*)calloc(N_PATIENTS, sizeof(TreatmentOutcome));
    if (!outcomes) {
        fprintf(stderr, "Failed to allocate memory for outcomes\n");
        free_population(patients);
        return 1;
    }
    
    // Run simulation
    printf("Phase 2: Running Monte Carlo simulation...\n");
    start_time = omp_get_wtime();
    simulate_population_parallel(patients, &protocol, outcomes, N_PATIENTS);
    double sim_time = omp_get_wtime() - start_time;
    printf("  Simulation completed in %.2f seconds\n", sim_time);
    printf("  Throughput: %.0f patients/second\n\n", N_PATIENTS / sim_time);
    
    // Calculate statistics
    printf("Phase 3: Analyzing results...\n");
    PopulationStatistics stats = calculate_statistics(outcomes, N_PATIENTS);
    
    // Print results
    print_statistics_report(&stats);
    print_comparison_table(&stats);
    
    // Performance summary
    printf("\n=========================================================\n");
    printf("                 COMPUTATIONAL PERFORMANCE\n");
    printf("=========================================================\n");
    printf("  Total runtime:        %.2f seconds\n", gen_time + sim_time);
    printf("  Patients/second:      %.0f\n", N_PATIENTS / (gen_time + sim_time));
    printf("  Core efficiency:      %.1f%%\n", 
           100.0 * N_PATIENTS / ((gen_time + sim_time) * max_threads * 1000));
    
    // Save results
    printf("\nSaving results...\n");
    save_results_csv(outcomes, N_PATIENTS, "dpp26_simulation_results.csv");
    save_statistics_json(&stats, "population_statistics.json");
    
    // Cleanup
    omp_destroy_lock(&progress_lock);
    free_population(patients);
    free(outcomes);
    
    printf("\nâœ“ Simulation complete. Results saved to CSV and JSON files.\n\n");
    
    return 0;
}