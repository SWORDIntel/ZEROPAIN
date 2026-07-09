import os

filepath = 'src/patient_simulation.py'
with open(filepath, 'r') as f:
    content = f.read()

import re

target_block_start = r"        # Volume of distribution adjusted for weight"
target_block_end = r"                g_sum \+= g_activation\n"

# Use regex with DOTALL to replace the block
pattern = re.compile(target_block_start + r".*?" + target_block_end, re.DOTALL)

replacement = """        # Volume of distribution adjusted for weight
        volume_dist = patient.weight * 0.7  # L/kg

        # PRE-COMPUTE COMPOUND CONSTANTS
        c_cache = []
        for compound, dose, freq in zip(compounds, protocol.doses, protocol.frequencies):
            interval = hours_per_day / freq
            dose_times = [i * interval for i in range(int(freq))]
            
            # CYP
            pathways = getattr(compound, 'metabolic_pathways', {"CYP2D6": 0.5, "CYP3A4": 0.5})
            pathway_sum = sum(ratio * patient.cyp_activity.get(enz, 1.0) for enz, ratio in pathways.items())
            pathway_sum = max(pathway_sum, 1e-3)
            adj_t_half = max(compound.t_half / pathway_sum, 0.1)
            
            # Receptors
            def _get_ki(rec):
                ki = getattr(compound, f'ki_{rec.lower()}', float('inf'))
                if ki == float('inf') and getattr(compound, 'receptor_type', 'MOR') == rec:
                    ki = compound.ki_orthosteric if compound.ki_orthosteric != float('inf') else (compound.ki_allosteric1 if compound.ki_allosteric1 != float('inf') else 50.0)
                return ki
                
            ki_mor = _get_ki('MOR')
            ki_dor = _get_ki('DOR')
            ki_kor = _get_ki('KOR')
            
            int_g = compound.intrinsic_activity * compound.g_protein_bias
            int_b = compound.intrinsic_activity * compound.beta_arrestin_bias
            
            c_cache.append({
                'dose_times': dose_times,
                'adj_t_half': adj_t_half,
                'bio': compound.bioavailability,
                'ki_mor': ki_mor,
                'ki_dor': ki_dor,
                'ki_kor': ki_kor,
                'int_g': int_g,
                'int_b': int_b,
                'dose': dose,
                'rev_tol': compound.reverses_tolerance,
                'tol_rate': getattr(compound, 'tolerance_rate', 0.1),
                'prev_with': getattr(compound, 'prevents_withdrawal', False)
            })

        # Simulate each timepoint
        for t_idx in range(n_timepoints):
            t_hours = t_idx * time_step
            t_days = t_hours / hours_per_day
            time_of_day = t_hours % hours_per_day

            total_analgesia = 0.0
            total_side_effects = 0.0
            g_sum = 0.0
            beta_sum = 0.0
            timepoint_dopamine = 0.0

            # Calculate contribution from each compound
            for c in c_cache:
                # Find time since last dose
                tsd = min([time_of_day - dt if time_of_day >= dt else time_of_day + hours_per_day - dt for dt in c['dose_times']])
                
                concentration = self.pk_model.calculate_concentration(
                    c['dose'], tsd, c['adj_t_half'], c['bio'], volume_dist
                )

                g_act = 0.0
                b_act = 0.0
                csens = concentration * patient.sensitivity

                if c['ki_mor'] != float('inf'):
                    g_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_mor'], c['int_g'])
                    b_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_mor'], c['int_b'])
                if c['ki_dor'] != float('inf'):
                    g_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_dor'], c['int_g'])
                    b_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_dor'], c['int_b'])
                if c['ki_kor'] != float('inf'):
                    g_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_kor'], c['int_g'])
                    b_act += self.pk_model.calculate_receptor_occupancy(csens, c['ki_kor'], c['int_b'])

                neurotransmitters = self.pk_model.calculate_neurotransmitter_release(g_act, b_act)
                for name, value in neurotransmitters.items():
                    neurotransmitter_totals[name] += value

                timepoint_dopamine += neurotransmitters.get('dopamine', 0.0)

                # Update tolerance
                if not c['rev_tol']:
                    dt_days = time_step / 24.0
                    exposure = c['tol_rate'] * b_act
                    tol_state = tol_model.update(tol_state, exposure, dt_days)
                    tolerance_level = tol_state.level

                if c['rev_tol'] and tolerance_level > 0:
                    tol_state.level *= 0.9995
                    tolerance_level = tol_state.level

                if c['rev_tol']:
                    eff_tol = max(0, tolerance_level * 0.3)
                elif c['prev_with']:
                    eff_tol = tolerance_level * 0.5
                else:
                    eff_tol = tolerance_level

                eff_tol = min(eff_tol, 0.95)

                analgesia = self.pk_model.calculate_analgesia(g_act, eff_tol)

                total_analgesia += analgesia
                total_side_effects += b_act
                g_sum += g_act
"""

new_content = pattern.sub(replacement, content)
with open(filepath, 'w') as f:
    f.write(new_content)

print("Patched!")
