#!/usr/bin/env python3
"""Exploratory model dose-response grid with MOR occupancy diagnostics."""
import argparse
import datetime
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
import torch
from tensor_simulation import TensorProtocolConfig, run_tensor_simulation
from run_mixed_population import profiles, save

SR_DOSES = (0.0, 1.25, 2.5, 5.0)
BUP_DOSES = (0.0, 0.25, 0.5, 1.0)
METRICS = ('analgesia_maintained_rate', 'withdrawal_rate', 'addiction_rate',
           'respiratory_depression_rate', 'overdose_rate', 'fatal_overdose_rate',
           'cardiac_fatal_rate', 'mortality_rate')


def markdown(data):
    lines = ["# Exploratory ZEROPAIN dose response", "",
             f"Device: {data['gpu'] or data['device']}; {data['total_patients']:,} virtual patients "
             f"across {len(data['scenarios'])} dose pairs and {len(data['profiles'])} profiles; "
             f"runtime {data['elapsed_seconds']:.1f}s.", "",
             "Doses are model inputs in mg per administration, twice daily. They are not "
             "recommended human doses. The PK/PD equations and response thresholds remain "
             "uncalibrated; receptor concentration units require correction before clinical "
             "interpretation. Equal profile weighting is an experimental design.", "",
             "Headroom screen: standard-profile p90 peak MOR occupancy <=80% and p50 "
             "last-day trough free MOR fraction >=20%. These are exploratory cutoffs.", "",
             "| SR-16435 | Buprenorphine | N | Standard pain p50 | Standard analgesia "
             "criterion | Standard peak MOR occupancy p90 | Standard trough free MOR p50 | "
             "Headroom screen | Pooled mortality criterion |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |"]
    for cell in data['scenarios']:
        if not cell.get('completed'):
            continue
        standard = cell['profiles']['standard_chronic_pain']
        n = cell['patients']
        occupancy = standard['percentiles']['peak_mor_occupancy']['p90']
        trough = standard['percentiles']['last_day_trough_free_mor_fraction']['p50']
        screen = 'yes' if occupancy <= 0.8 and trough >= 0.2 else 'no'
        lines.append(f"| {cell['sr_dose_mg']:.2f} | {cell['bup_dose_mg']:.2f} | "
                     f"{n:,} | {standard['percentiles']['pain_score']['p50']:.2f} | "
                     f"{100*standard['analgesia_maintained_rate']:.3f}% | "
                     f"{100*occupancy:.1f}% | {100*trough:.1f}% | {screen} | "
                     f"{100*cell['event_counts']['mortality_rate']/n:.2f}% |")
    lines += ['', 'The occupancy measure includes all MOR-binding compounds in the model. '
              'High-risk street-exposure profiles can saturate receptors independently of '
              'the two administered components. Patient-level outcomes are not persisted.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    parser.add_argument('--n-per-profile', type=int, default=100_000)
    parser.add_argument('--output-dir', default='runs/dose_grid')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.n_per_profile < 1:
        parser.error('n-per-profile must be positive')
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA is required for the cloud dose grid')
    torch.set_num_threads(4)
    configs, adjustments = profiles()
    if args.smoke:
        configs = configs[:2]
        pairs = ((0.0, 0.0), (2.5, 0.5))
        args.n_per_profile = 32
    else:
        pairs = tuple((sr, bup) for sr in SR_DOSES for bup in BUP_DOSES)
    output = Path(args.output_dir)
    started = time.monotonic()
    data = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'device': args.device,
            'gpu': torch.cuda.get_device_name(0) if args.device == 'cuda' else None,
            'torch_version': torch.__version__, 'n_per_profile': args.n_per_profile,
            'profiles': [cfg.name for cfg in configs],
            'probability_adjustments': adjustments,
            'dose_grid_mg': {'SR-16435': list(SR_DOSES), 'Buprenorphine': list(BUP_DOSES)},
            'total_patients': 0, 'elapsed_seconds': 0,
            'scenarios': [], 'status': 'running'}
    for sr, bup in pairs:
        protocol = TensorProtocolConfig(['SR-16435', 'Buprenorphine'],
                                        [sr, bup], [2.0, 2.0])
        cell = {'sr_dose_mg': sr, 'bup_dose_mg': bup, 'patients': 0,
                'profiles': {}, 'event_counts': {}, 'completed': False}
        data['scenarios'].append(cell)
        for idx, cfg in enumerate(configs):
            seed = 42100 + idx
            torch.manual_seed(seed)
            result = run_tensor_simulation(
                total_patients=args.n_per_profile, protocol=protocol, cohort=cfg,
                chunk_size=args.n_per_profile, device=args.device,
                seed=seed, verbose=False).to_dict()
            cell['profiles'][cfg.name] = result
            cell['patients'] += result['total_patients']
            data['total_patients'] += result['total_patients']
            for metric in METRICS:
                rate = result[metric]
                assert math.isfinite(rate) and 0 <= rate <= 1, (metric, rate)
                cell['event_counts'][metric] = cell['event_counts'].get(metric, 0) + round(
                    rate * result['total_patients'])
            data['elapsed_seconds'] = time.monotonic() - started
            save(output / 'results_dose_grid.json', data)
            print(f"DOSE SR={sr:g} BUP={bup:g} PROFILE={cfg.name} "
                  f"TOTAL={data['total_patients']:,} ELAPSED={data['elapsed_seconds']:.1f}s",
                  flush=True)
        cell['completed'] = True
        save(output / 'results_dose_grid.json', data)
    data['status'] = 'completed'
    data['elapsed_seconds'] = time.monotonic() - started
    save(output / 'results_dose_grid.json', data)
    (output / 'REPORT_DOSE_GRID.md').write_text(markdown(data))
    assert len(data['scenarios']) == len(pairs)
    assert all(cell['completed'] for cell in data['scenarios'])
    print('RESULT ' + json.dumps({'patients': data['total_patients'],
          'elapsed_seconds': data['elapsed_seconds'], 'gpu': data['gpu'],
          'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()
