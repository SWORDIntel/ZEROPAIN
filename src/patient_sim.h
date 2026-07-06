#ifndef PATIENT_SIM_H
#define PATIENT_SIM_H

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <omp.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define SIMULATION_DAYS 90
#define TIMESTEPS_PER_DAY 96
#define BATCH_SIZE 256
#define MAX_THREADS 64

#define COST_PER_DAY_DPP26 1.50f
#define PAIN_CONTROL_FAILURE 6.5f
#define TRIAL_PERIOD_DAYS 7
#define DAYS_PER_YEAR 365.25f
#define QALY_UTILITY_GAIN_FACTOR 0.15f
#define TOLERANCE_THRESHOLD 0.5f
#define ADDICTION_RISK_THRESHOLD 2.0f

#define clamp(val, min, max) ((val) < (min) ? (min) : ((val) > (max) ? (max) : (val)))

typedef enum {
    ACUTE_POSTOP = 0,
    CHRONIC_LOW_BACK = 1,
    NEUROPATHIC = 2,
    CHRONIC_CANCER = 3,
    BREAKTHROUGH = 4
} PainType;

typedef enum {
    NORMAL_METABOLIZER = 0,
    POOR_METABOLIZER = 1,
    RAPID_METABOLIZER = 2,
    ULTRA_RAPID_METABOLIZER = 3
} MetabolizerPhenotype;

typedef struct {
    float sr17018_dose;
    float sr14968_dose;
    float dpp26_dose;
} Protocol;

typedef struct {
    int patient_id;
    uint8_t age;
    uint8_t sex;
    float weight;
    float bmi;
    int pain_type;
    float baseline_pain_score;
    uint16_t pain_duration_months;
    bool prior_opioid_use;
    float prior_opioid_dose_mme;
    int risk_category;
    bool addiction_history;
    bool mental_health_comorbidity;
    bool respiratory_disease;
    float renal_function;
    float hepatic_function;
    int cyp2d6_phenotype;
    int cyp3a4_phenotype;
    bool oprm1_variant;
    bool comt_variant;
    float adherence_probability;
} PatientCharacteristics;

typedef struct {
    int patient_id;
    float daily_pain_scores[SIMULATION_DAYS];
    float analgesia_achieved[SIMULATION_DAYS];
    bool treatment_success;
    int discontinuation_day;
    char discontinuation_reason[32];
    float avg_pain_reduction;
    bool tolerance_developed;
    bool addiction_signs;
    bool withdrawal_occurred;
    int adverse_event_count;
    float final_tolerance_level;
    float total_cost;
    float qaly_gained;
} TreatmentOutcome;

typedef struct {
    const char* name;
    float ki_orthosteric;
    float ki_allosteric1;
    float ki_allosteric2;
    float g_protein_bias;
    float beta_arrestin_bias;
    float t_half;
    float bioavailability;
    float intrinsic_activity;
    float tolerance_rate;
    bool prevents_withdrawal;
    bool reverses_tolerance;
} CompoundProfile;

static const CompoundProfile SR17018 = {
    .name = "SR-17018",
    .ki_orthosteric = INFINITY,
    .ki_allosteric1 = 26.0f,
    .ki_allosteric2 = 100.0f,
    .g_protein_bias = 8.2f,
    .beta_arrestin_bias = 0.01f,
    .t_half = 7.0f,
    .bioavailability = 0.7f,
    .intrinsic_activity = 0.38f,
    .tolerance_rate = 0.0f,
    .prevents_withdrawal = true,
    .reverses_tolerance = true
};

static const CompoundProfile SR14968 = {
    .name = "SR-14968",
    .ki_orthosteric = INFINITY,
    .ki_allosteric1 = 10.0f,
    .ki_allosteric2 = 50.0f,
    .g_protein_bias = 10.0f,
    .beta_arrestin_bias = 0.1f,
    .t_half = 12.0f,
    .bioavailability = 0.8f,
    .intrinsic_activity = 0.65f,
    .tolerance_rate = 0.15f,
    .prevents_withdrawal = false,
    .reverses_tolerance = false
};

static const CompoundProfile DPP26 = {
    .name = "DPP-26",
    .ki_orthosteric = 10.0f,
    .ki_allosteric1 = INFINITY,
    .ki_allosteric2 = INFINITY,
    .g_protein_bias = 1.0f,
    .beta_arrestin_bias = 0.1f,
    .t_half = 4.0f,
    .bioavailability = 0.5f,
    .intrinsic_activity = 0.9f,
    .tolerance_rate = 0.4f,
    .prevents_withdrawal = true,
    .reverses_tolerance = false
};

typedef struct {
    float success_rate;
    float tolerance_rate;
    float addiction_rate;
    float withdrawal_rate;
    float adverse_event_rate;
    float avg_pain_score;
    float avg_analgesia;
    float avg_cost;
    float avg_qaly;
    int discontinuation_reasons[4]; // 0: none, 1: inadequate_analgesia, 2: non_adherence, 3: trial_failure
} PopulationStatistics;

static inline PopulationStatistics calculate_statistics(const TreatmentOutcome* outcomes, int n) {
    PopulationStatistics stats = {0};
    double pain_sum = 0, analgesia_sum = 0, cost_sum = 0, qaly_sum = 0;
    int success_cnt = 0, tol_cnt = 0, add_cnt = 0, wd_cnt = 0, ae_cnt = 0;
    
    for (int i = 0; i < n; i++) {
        const TreatmentOutcome* o = &outcomes[i];
        if (o->treatment_success) success_cnt++;
        if (o->tolerance_developed) tol_cnt++;
        if (o->addiction_signs) add_cnt++;
        if (o->withdrawal_occurred) wd_cnt++;
        if (o->adverse_event_count > 0) ae_cnt++;
        
        // daily averages
        float patient_pain = 0;
        float patient_analgesia = 0;
        for (int d = 0; d < SIMULATION_DAYS; d++) {
            patient_pain += o->daily_pain_scores[d];
            patient_analgesia += o->analgesia_achieved[d];
        }
        pain_sum += patient_pain / SIMULATION_DAYS;
        analgesia_sum += patient_analgesia / SIMULATION_DAYS;
        cost_sum += o->total_cost;
        qaly_sum += o->qaly_gained;
        
        if (strcmp(o->discontinuation_reason, "inadequate_analgesia") == 0) {
            stats.discontinuation_reasons[1]++;
        } else if (strcmp(o->discontinuation_reason, "non_adherence") == 0) {
            stats.discontinuation_reasons[2]++;
        } else if (strcmp(o->discontinuation_reason, "trial_failure") == 0) {
            stats.discontinuation_reasons[3]++;
        } else if (o->discontinuation_day < SIMULATION_DAYS) {
            stats.discontinuation_reasons[0]++;
        }
    }
    
    stats.success_rate = (float)success_cnt / n;
    stats.tolerance_rate = (float)tol_cnt / n;
    stats.addiction_rate = (float)add_cnt / n;
    stats.withdrawal_rate = (float)wd_cnt / n;
    stats.adverse_event_rate = (float)ae_cnt / n;
    stats.avg_pain_score = (float)(pain_sum / n);
    stats.avg_analgesia = (float)(analgesia_sum / n);
    stats.avg_cost = (float)(cost_sum / n);
    stats.avg_qaly = (float)(qaly_sum / n);
    
    return stats;
}

static inline void print_statistics_report(const PopulationStatistics* stats) {
    printf("\n=========================================================\n");
    printf("                  SIMULATION OUTCOMES SUMMARY\n");
    printf("=========================================================\n");
    printf("  Treatment Success Rate:     %.2f%%\n", stats->success_rate * 100.0);
    printf("  Tolerance Development Rate: %.2f%%\n", stats->tolerance_rate * 100.0);
    printf("  Addiction Rate:             %.2f%%\n", stats->addiction_rate * 100.0);
    printf("  Withdrawal Rate:            %.2f%%\n", stats->withdrawal_rate * 100.0);
    printf("  Adverse Event Rate:         %.2f%%\n", stats->adverse_event_rate * 100.0);
    printf("  Average Pain Score:         %.2f / 10\n", stats->avg_pain_score);
    printf("  Average Analgesia Level:    %.2f%%\n", stats->avg_analgesia * 100.0);
    printf("  Average Total Cost:         $%.2f\n", stats->avg_cost);
    printf("  Average QALYs Gained:       %.4f\n", stats->avg_qaly);
    printf("---------------------------------------------------------\n");
    printf("  Discontinuation Breakdown:\n");
    printf("    Inadequate Analgesia:     %d\n", stats->discontinuation_reasons[1]);
    printf("    Non-Adherence:            %d\n", stats->discontinuation_reasons[2]);
    printf("    Trial Failure:            %d\n", stats->discontinuation_reasons[3]);
    printf("    Other Reasons:            %d\n", stats->discontinuation_reasons[0]);
}

static inline void print_comparison_table(const PopulationStatistics* stats) {
    printf("\n=========================================================\n");
    printf("            CLINICAL METRICS COMPARISON VS METADATA\n");
    printf("=========================================================\n");
    printf("  Metric                  DPP-26 Protocol    Standard Opioids\n");
    printf("  ---------------------------------------------------------\n");
    printf("  Success Rate            %6.2f%%            45.00%%\n", stats->success_rate * 100.0);
    printf("  Tolerance Rate          %6.2f%%            75.00%%\n", stats->tolerance_rate * 100.0);
    printf("  Addiction Rate          %6.2f%%            12.00%%\n", stats->addiction_rate * 100.0);
    printf("  Withdrawal Rate         %6.2f%%            85.00%%\n", stats->withdrawal_rate * 100.0);
    printf("  Avg Pain Score          %6.2f              4.80\n", stats->avg_pain_score);
    printf("=========================================================\n");
}

static inline void save_results_csv(const TreatmentOutcome* outcomes, int n, const char* filepath) {
    FILE* f = fopen(filepath, "w");
    if (!f) return;
    fprintf(f, "patient_id,treatment_success,discontinuation_day,discontinuation_reason,avg_pain_reduction,tolerance_developed,addiction_signs,withdrawal_occurred,adverse_event_count,final_tolerance_level,total_cost,qaly_gained\n");
    for (int i = 0; i < n; i++) {
        const TreatmentOutcome* o = &outcomes[i];
        fprintf(f, "%d,%d,%d,%s,%.4f,%d,%d,%d,%d,%.4f,%.2f,%.4f\n",
                o->patient_id, o->treatment_success, o->discontinuation_day, o->discontinuation_reason,
                o->avg_pain_reduction, o->tolerance_developed, o->addiction_signs, o->withdrawal_occurred,
                o->adverse_event_count, o->final_tolerance_level, o->total_cost, o->qaly_gained);
    }
    fclose(f);
}

static inline void save_statistics_json(const PopulationStatistics* stats, const char* filepath) {
    FILE* f = fopen(filepath, "w");
    if (!f) return;
    fprintf(f, "{\n");
    fprintf(f, "  \"success_rate\": %.4f,\n", stats->success_rate);
    fprintf(f, "  \"tolerance_rate\": %.4f,\n", stats->tolerance_rate);
    fprintf(f, "  \"addiction_rate\": %.4f,\n", stats->addiction_rate);
    fprintf(f, "  \"withdrawal_rate\": %.4f,\n", stats->withdrawal_rate);
    fprintf(f, "  \"adverse_event_rate\": %.4f,\n", stats->adverse_event_rate);
    fprintf(f, "  \"avg_pain_score\": %.4f,\n", stats->avg_pain_score);
    fprintf(f, "  \"avg_analgesia\": %.4f,\n", stats->avg_analgesia);
    fprintf(f, "  \"avg_cost\": %.4f,\n", stats->avg_cost);
    fprintf(f, "  \"avg_qaly\": %.4f,\n", stats->avg_qaly);
    fprintf(f, "  \"discontinuation_inadequate_analgesia\": %d,\n", stats->discontinuation_reasons[1]);
    fprintf(f, "  \"discontinuation_non_adherence\": %d,\n", stats->discontinuation_reasons[2]);
    fprintf(f, "  \"discontinuation_trial_failure\": %d,\n", stats->discontinuation_reasons[3]);
    fprintf(f, "  \"discontinuation_other\": %d\n", stats->discontinuation_reasons[0]);
    fprintf(f, "}\n");
    fclose(f);
}

#endif // PATIENT_SIM_H
