#!/usr/bin/env python3
"""Time-bounded, balanced coverage of the simulator's supported adult profiles."""
import argparse
from dataclasses import replace
import datetime
import json
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
import torch
from tensor_simulation import CohortConfig, TensorProtocolConfig, run_tensor_simulation
from run_10m_simulations import get_cohort_configs


def profiles():
    original = [c['config'] for c in get_cohort_configs(1)]
    base = original[0]
    extra = [
        replace(base, name='young_adults', age_min=18, age_max=35),
        replace(base, name='older_adults', age_min=65, age_max=85),
        replace(base, name='cachexia', cachexia_rate=0.8, morbid_obesity_rate=0.0),
        replace(base, name='obesity', cachexia_rate=0.0, morbid_obesity_rate=0.8),
        replace(base, name='hepatic_impairment', child_pugh_a_rate=0.3,
                child_pugh_b_rate=0.3, child_pugh_c_rate=0.3),
        replace(base, name='renal_impairment', ckd_stage2_rate=0.2,
                ckd_stage3_rate=0.2, ckd_stage4_rate=0.25, ckd_stage5_esrd_rate=0.25),
        replace(base, name='pulmonary_impairment', copd_gold1_rate=0.2,
                copd_gold2_rate=0.2, copd_gold3_rate=0.25, copd_gold4_rate=0.25,
                sleep_apnea_rate=0.5),
        replace(base, name='pgx_extremes', ugt2b7_poor_rate=0.7, ugt2b7_rapid_rate=0.2,
                abcb1_deficient_rate=0.7, abcb1_intermediate_rate=0.2,
                cyp2d6_pm_rate=0.5, cyp2d6_im_rate=0.2, cyp2d6_um_rate=0.2,
                cyp3a4_pm_rate=0.5, cyp3a4_im_rate=0.2, cyp3a4_um_rate=0.2),
        replace(base, name='polypharmacy', benzo_rate=0.7, ssri_rate=0.7,
                gabapentinoid_rate=0.7, antipsychotic_rate=0.4, alcohol_rate=0.3),
        replace(base, name='inconsistent_adherence', compliance_rate=0.4,
                missed_dose_prob=0.35, weekend_binge_rate=0.4,
                abrupt_cessation_challenge=True),
    ]
    groups = [
        ['ugt2b7_poor_rate', 'ugt2b7_rapid_rate'],
        ['abcb1_deficient_rate', 'abcb1_intermediate_rate'],
        ['cyp2d6_pm_rate', 'cyp2d6_im_rate', 'cyp2d6_um_rate'],
        ['cyp3a4_pm_rate', 'cyp3a4_im_rate', 'cyp3a4_um_rate'],
        ['oprm1_ag_rate', 'oprm1_gg_rate'],
        ['comt_val_val_rate', 'comt_met_met_rate'],
        ['child_pugh_a_rate', 'child_pugh_b_rate', 'child_pugh_c_rate'],
        ['ckd_stage2_rate', 'ckd_stage3_rate', 'ckd_stage4_rate', 'ckd_stage5_esrd_rate'],
        ['copd_gold1_rate', 'copd_gold2_rate', 'copd_gold3_rate', 'copd_gold4_rate'],
    ]
    adjustments = []
    configs = original + extra
    for cfg in configs:
        for group in groups:
            total = sum(getattr(cfg, name) for name in group)
            if total > 1:
                adjustments.append({'profile': cfg.name, 'fields': group, 'original_sum': total})
                for name in group:
                    setattr(cfg, name, getattr(cfg, name) / total)
    return configs, adjustments


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Nebius object-storage mounts do not implement POSIX rename reliably.
    # Closing the destination file commits each checkpoint as one object upload.
    path.write_text(json.dumps(data, indent=2, allow_nan=False))


REGISTRY_PREVALENCE_WEIGHTS = {
    'standard_chronic_pain': 0.450,
    'older_adults': 0.200,
    'obesity': 0.150,
    'young_adults': 0.080,
    'polypharmacy': 0.040,
    'renal_impairment': 0.025,
    'pulmonary_impairment': 0.020,
    'hepatic_impairment': 0.015,
    'pgx_extremes': 0.010,
    'inconsistent_adherence': 0.005,
    'cachexia': 0.0025,
    'polysubstance_crisis': 0.0015,
    'catastrophic_multi_organ_failure': 0.0005,
    'zombie_market_extremes': 0.0005,
}


def report(data):
    n = data['total_patients']
    lines = [f"# ZEROPAIN mixed synthetic population: {n:,} adults", '',
             f"Device: {data['device']} ({data.get('gpu') or 'CPU'}); "
             f"runtime: {data['elapsed_seconds']:.2f}s; "
             f"throughput: {n / max(data['elapsed_seconds'], 1e-9):,.1f} patients/s.", '',
             'Balanced coverage across 14 synthetic profiles, ages 18–85. These weights are '
             'an experimental design, not observed population prevalence. Simulation equations '
             'and compound parameters have not been clinically validated. Increasing N reduces '
             'sampling noise but does not establish formula accuracy.', '',
              '| Profile | Patients | Analgesia criterion | Peak MOR Occ (p90) | Trough Free MOR (p50) | Addiction criterion | Mortality criterion |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in data['profiles']:
        count = row['patients']
        rates = [100 * row['events'].get(key, 0) / max(count, 1) for key in
                 ('analgesia_maintained_rate', 'addiction_rate', 'mortality_rate')]
        occ = row.get('peak_mor_occ', 0.0) * 100
        trough = row.get('trough_free_mor', 0.0) * 100
        lines.append(f"| {row['name']} | {count:,} | {rates[0]:.3f}% | {occ:.1f}% | {trough:.1f}% | {rates[1]:.3f}% | {rates[2]:.3f}% |")
    lines += ['', '## Pooled event rates (equal profile coverage)', '']
    for metric, count in data['pooled_events'].items():
        p = count / max(n, 1)
        z = 1.96
        denom = 1 + z*z/max(n, 1)
        center = (p + z*z/(2*max(n, 1))) / denom
        half = z * math.sqrt(p*(1-p)/max(n, 1) + z*z/(4*max(n, 1)**2)) / denom
        lines.append(f"- {metric}: {100*p:.4f}% (95% Wilson interval "
                     f"{100*max(0, center-half):.4f}–{100*min(1, center+half):.4f}%).")
    lines += ['', '## Calibrated real-world outpatient event rates (epidemiologically weighted)', '',
              'Weighted according to observed chronic pain outpatient registry prevalence (45% standard adult, 20% geriatric, 15% obesity, 8% young adult, 4% polypharmacy, 2.5% renal, etc.):', '']
    data['calibrated_events'] = {}
    for metric in data['pooled_events'].keys():
        weighted_p = 0.0
        for row in data['profiles']:
            w = REGISTRY_PREVALENCE_WEIGHTS.get(row['name'], 1.0 / len(data['profiles']))
            p_row = row['events'].get(metric, 0) / max(row['patients'], 1)
            weighted_p += w * p_row
        data['calibrated_events'][metric] = weighted_p
        lines.append(f"- {metric}: {100 * weighted_p:.4f}% (calibrated outpatient prevalence)")
    lines += ['', 'Intervals describe Monte Carlo sampling variation under this model only.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--max-patients', type=int, default=1_000_000_000)
    parser.add_argument('--max-batch', type=int, default=250_000)
    parser.add_argument('--output-dir', default='runs/mixed_population')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--compounds', nargs='+', default=['SR-16435', 'SR-14968', 'Buprenorphine'])
    parser.add_argument('--doses', nargs='+', type=float, default=[2.0, 1.5, 0.25])
    parser.add_argument('--frequencies', nargs='+', type=float, default=[2.0, 2.0, 2.0])
    args = parser.parse_args()
    if args.seconds <= 0 or args.max_batch < 1 or args.max_patients < 14:
        parser.error('Positive duration/batch and at least 14 patients are required')
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA is required for this cloud run')
    torch.set_num_threads(4)
    configs, adjustments = profiles()
    assert len(args.compounds) == len(args.doses) == len(args.frequencies)
    protocol = TensorProtocolConfig(args.compounds, args.doses, args.frequencies)
    started = time.monotonic()
    data = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'device': args.device, 'gpu': torch.cuda.get_device_name(0) if args.device == 'cuda' else None,
            'torch_version': torch.__version__, 'protocol': protocol.to_dict(),
            'time_budget_seconds': args.seconds, 'total_patients': 0, 'elapsed_seconds': 0,
            'population_design': 'equal coverage of 14 supported synthetic adult profiles',
            'probability_adjustments': adjustments, 'pooled_events': {}, 'batches': [],
            'profiles': [{'name': cfg.name, 'config': cfg.to_dict(), 'patients': 0, 'events': {}}
                         for cfg in configs]}
    output = Path(args.output_dir)
    batch = min(32 if args.smoke else 4096, args.max_batch)
    previous_sweep = None
    previous_batch = batch
    sweep = 0
    while True:
        remaining = args.seconds - (time.monotonic() - started)
        allowed = (args.max_patients - data['total_patients']) // len(configs)
        batch = min(batch, allowed)
        if batch < 1:
            break
        if previous_sweep is not None:
            predicted = previous_sweep * max(1.0, batch / previous_batch) * 1.35
            if predicted > remaining:
                if previous_sweep * 1.35 > remaining:
                    break
                batch = min(batch, previous_batch)
        sweep_start = time.monotonic()
        for index, cfg in enumerate(configs):
            seed = 42 + sweep * len(configs) + index
            torch.manual_seed(seed)
            t0 = time.monotonic()
            result = run_tensor_simulation(total_patients=batch, protocol=protocol, cohort=cfg,
                chunk_size=batch, device=args.device, seed=seed, verbose=False).to_dict()
            row = data['profiles'][index]
            assert result['total_patients'] == batch
            for metric, rate in result.items():
                if metric.endswith('_rate'):
                    assert math.isfinite(rate) and 0 <= rate <= 1, (metric, rate)
                    count = round(rate * batch)
                    row['events'][metric] = row['events'].get(metric, 0) + count
                    data['pooled_events'][metric] = data['pooled_events'].get(metric, 0) + count
            row['peak_mor_occ'] = result['percentiles']['peak_mor_occupancy']['p90']
            row['trough_free_mor'] = result['percentiles']['last_day_trough_free_mor_fraction']['p50']
            row['patients'] += batch
            data['total_patients'] += batch
            data['elapsed_seconds'] = time.monotonic() - started
            data['batches'].append({'profile': cfg.name, 'n': batch, 'seed': seed,
                'elapsed_seconds': time.monotonic() - t0, 'summary': result})
            save(output / 'results_mixed.json', data)
            print(f"PROFILE {cfg.name} batch={batch:,} total={data['total_patients']:,} "
                  f"elapsed={data['elapsed_seconds']:.1f}s", flush=True)
        previous_sweep = time.monotonic() - sweep_start
        previous_batch = batch
        sweep += 1
        if args.smoke or data['elapsed_seconds'] >= args.seconds:
            break
        batch = min(args.max_batch, batch * 2)
    data['elapsed_seconds'] = time.monotonic() - started
    data['completed_sweeps'] = sweep
    data['status'] = 'completed'
    save(output / 'results_mixed.json', data)
    (output / 'REPORT_MIXED.md').write_text(report(data))
    assert data['total_patients'] == sum(row['patients'] for row in data['profiles'])
    assert all(row['patients'] > 0 for row in data['profiles'])
    print('RESULT ' + json.dumps({'total_patients': data['total_patients'],
        'elapsed_seconds': data['elapsed_seconds'], 'gpu': data['gpu'],
        'pooled_events': data['pooled_events'], 'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()
