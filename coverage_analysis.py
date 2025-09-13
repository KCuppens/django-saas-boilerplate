#!/usr/bin/env python3
"""Calculate coverage improvement potential."""

# Current state
current_total_lines = 2751
current_covered = 1755
current_coverage = 63.79
target_coverage = 80.0

# Files with highest impact (file, total_lines, missing_lines, current_coverage)
high_impact_files = [
    ("emails/views.py", 101, 101, 0.0),
    ("ops/tasks.py", 122, 122, 0.0),
    ("files/views.py", 117, 77, 34.19),
    ("core/tasks.py", 41, 41, 0.0),
    ("ops/metrics.py", 92, 80, 13.04),
    ("core/middleware.py", 78, 51, 34.62),
    ("featureflags/helpers.py", 63, 30, 52.38),
    ("emails/admin.py", 41, 13, 68.29),
    ("ops/views.py", 32, 23, 28.12),
    ("files/services.py", 96, 18, 81.25),
    ("emails/services.py", 145, 17, 88.28),
    ("accounts/serializers.py", 111, 18, 83.78),
    ("accounts/views.py", 136, 16, 88.24),
]

print("COVERAGE IMPROVEMENT PLAN")
print("=" * 70)
print(f"Current: {current_coverage:.2f}% ({current_covered}/{current_total_lines})")
print(f"Target:  {target_coverage:.2f}%")

lines_needed = int((target_coverage / 100) * current_total_lines) - current_covered
print(f"Lines needed to cover: {lines_needed}")
print()

print("HIGH IMPACT OPPORTUNITIES")
print("-" * 70)

cumulative_coverage = current_coverage
cumulative_covered = current_covered

for file_path, _, missing_lines, current_cov in high_impact_files:
    # Estimate realistic coverage improvement (80% of missing lines)
    if current_cov == 0:
        potential_new_covered = int(missing_lines * 0.8)  # 80% for 0% files
    elif current_cov < 50:
        potential_new_covered = int(missing_lines * 0.7)  # 70% for low coverage
    else:
        potential_new_covered = int(missing_lines * 0.6)  # 60% for moderate coverage

    new_cumulative_covered = cumulative_covered + potential_new_covered
    new_coverage = (new_cumulative_covered / current_total_lines) * 100
    impact = new_coverage - cumulative_coverage

    print(
        f"{file_path:25} | Missing: {missing_lines:3} | "
        f"+{impact:5.2f}% | Total: {new_coverage:5.2f}%"
    )

    cumulative_coverage = new_coverage
    cumulative_covered = new_cumulative_covered

    if new_coverage >= target_coverage:
        print(f"\nTarget {target_coverage}% reached!")
        break

print("\n" + "=" * 70)
