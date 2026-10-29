import csv, os

data_dir = 'data'

# Check races years and count
with open(os.path.join(data_dir, 'races.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    years = set()
    count = 0
    for row in reader:
        years.add(row[1])  # year column
        count += 1
print(f'Races years: {sorted(years)}')
print(f'Total races: {count}')

# Check row counts for key tables
for f in sorted(os.listdir(data_dir)):
    if f.endswith('.csv'):
        path = os.path.join(data_dir, f)
        with open(path, 'r', encoding='utf-8-sig') as fh:
            reader = csv.reader(fh)
            header = next(reader)
            row_count = sum(1 for _ in reader)
            print(f'{f}: {row_count} rows')

# Sample data from key tables
print("\n--- Sample races.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'races.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample drivers.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'drivers.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample results.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'results.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample qualifying.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'qualifying.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample pit_stops.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'pit_stops.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample lap_times.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'lap_times.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample constructors.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'constructors.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample driver_standings.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'driver_standings.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)

print("\n--- Sample constructor_standings.csv (first 3 rows) ---")
with open(os.path.join(data_dir, 'constructor_standings.csv'), 'r', encoding='utf-8-sig') as fh:
    reader = csv.reader(fh)
    header = next(reader)
    for i, row in enumerate(reader):
        if i >= 3: break
        print(row)