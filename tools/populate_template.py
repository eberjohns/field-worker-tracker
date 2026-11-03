from pathlib import Path
import openpyxl
from datetime import date

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "docs/import-templates/FieldWorkerTracker_Import_Template_v1.0.xlsx"
wb = openpyxl.load_workbook(TEMPLATE_PATH)

# 1. Groups Sheet
ws_groups = wb["Groups"]
# Clear existing data rows starting from row 5
for r in range(5, ws_groups.max_row + 1):
    for c in range(1, ws_groups.max_column + 1):
        ws_groups.cell(row=r, column=c).value = None

groups_data = [
    (1, "102", "Dr. Moopens (Aster)"),
    (2, "104", "Dubai Developments - DIRE"),
    (3, "106", "Al Futtaim Real Estate properties - AFRE"),
    (4, "107", "Unilever Gulf FZE - Indoor and Landscaping AMC"),
    (5, "999", "Miscellenious"),
]
for idx, (num, code, name) in enumerate(groups_data, start=5):
    ws_groups.cell(row=idx, column=1, value=None)
    ws_groups.cell(row=idx, column=2, value=code)
    ws_groups.cell(row=idx, column=3, value=name)

# 2. Zones Sheet
ws_zones = wb["Zones"]
for r in range(5, ws_zones.max_row + 1):
    for c in range(1, ws_zones.max_column + 1):
        ws_zones.cell(row=r, column=c).value = None

zones_data = [
    (1, "1", "Al Qusais / Deira"),
    (2, "2", "Bur Dubai / Business Bay"),
    (3, "3", "Al Quoz / Jumeira upto 5th Interchange"),
    (4, "5", "Jebel Ali"),
]
for idx, (num, code, name) in enumerate(zones_data, start=5):
    ws_zones.cell(row=idx, column=1, value=None)
    ws_zones.cell(row=idx, column=2, value=code)
    ws_zones.cell(row=idx, column=3, value=name)

# 3. Worksites Sheet
# Raw list from Site_Grouping.xlsx
worksites_raw = [
    ("22B10202", "Dr. Moopen's - Business Bay HQ 33rd Floor - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22B10203", "Dr. Moopen's - Business Bay HQ 34th Floor - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22B10215", "Dr. Moopen's - Aster DM - Al Hudaiba Bldng 6th Floor - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22B10216", "Dr. Moopen's - Aster DM - Al Diyafah Building - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22B10218", "Dr. Moopen's - Aster DM - Al Hudaiba Bldng - 3rd Floor - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22B10219", "Dr. Moopen's - Aster DM - Aspect Tower - 38th Level - Indoor Service AMC", "102", "2", "Direct", 45000.0),
    ("22A10401", "Dubai Developments - DIRE - Al Hubaida Awards Bldg (Block A) - Outdoor AMC", "104", "2", "Direct", 120000.0),
    ("22B10401", "Dubai Developments - DIRE - Al Hubaida Awards Bldg (Block A) - Indoor AMC", "104", "2", "Direct", 55000.0),
    ("22A10601", "AFM - Real Estate Properties - AL DHIYAFA VILLAGE - Outdoor AMC", "106", "2", "Direct", 110000.0),
    ("32A10602", "AFM - Real Estate Properties - JUMEIRAH / SAFA VILLAS - Outdoor AMC", "106", "3", "Direct", 150000.0),
    ("32B10603", "AFM - Real Estate Properties - AL QUOZE BUSINESS CENTER - Indoor AMC", "106", "3", "Direct", 40000.0),
    ("12A10604", "AFM - Real Estate Properties - DAR AL BUTEEN I - Outdoor AMC", "106", "1", "Direct", 85000.0),
    ("12B10604", "AFM - Real Estate Properties - DAR AL BUTEEN I - Indoor AMC", "106", "1", "Direct", 35000.0),
    ("12A10605", "AFM - Real Estate Properties - DAR AL BUTEEN II - Outdoor AMC", "106", "1", "Direct", 85000.0),
    ("12B10605", "AFM - Real Estate Properties - DAR AL BUTEEN II - Indoor AMC", "106", "1", "Direct", 35000.0),
    ("12A10606", "AFM - Real Estate Properties - RIGGA HEAD OFFICE - Outdoor AMC", "106", "1", "Direct", 95000.0),
    ("12B10606", "AFM - Real Estate Properties - RIGGA HEAD OFFICE - Indoor AMC", "106", "1", "Direct", 45000.0),
    ("12A10607", "AFM - Real Estate Properties - DAR AL MUTEENA - Outdoor AMC", "106", "1", "Direct", 90000.0),
    ("12A10608", "AFM - Real Estate Properties - DAR AL KHABEESI - Outdoor AMC", "106", "1", "Direct", 85000.0),
    ("12B10608", "AFM - Real Estate Properties - DAR AL KHABEESI - Indoor AMC", "106", "1", "Direct", 35000.0),
    ("12A10609", "AFM - Real Estate Properties - DAR AL MURAQABAT - Outdoor AMC", "106", "1", "Direct", 80000.0),
    ("12B10609", "AFM - Real Estate Properties - DAR AL MURAQABAT - Indoor AMC", "106", "1", "Direct", 30000.0),
    ("12A10611", "AFM - Real Estate Properties - AL GHUSSAIS HOUSING COMPLEX - Outdoor AMC", "106", "1", "Direct", 110000.0),
    ("12A10612", "AFM - Real Estate Properties - VILLA # 13 AL BADIA - Outdoor AMC", "106", "1", "Direct", 60000.0),
    ("52A10613", "AFM - Real Estate Properties - LABOUR CAMP DIP - Outdoor AMC", "106", "5", "Direct", 75000.0),
    ("22A10614", "AFM - Real Estate Properties -KARAMA BUILDING - Outdoor AMC", "106", "2", "Direct", 70000.0),
    ("52A10701", "Unilever - UHD AL JAFZA - Outdoor AMC", "107", "5", "Indirect", 130000.0),
    ("52B10701", "Unilever - UHD AL JAFZA - Indoor AMC", "107", "5", "Indirect", 50000.0),
    ("52C10701", "Unilever - UHD AL JAFZA - Water Feature AMC", "107", "5", "Indirect", 30000.0),
    ("52A10703", "Unilever - DPC - Outdoor AMC", "107", "5", "Indirect", 95000.0),
    ("52B10703", "Unilever - DPC - Indoor AMC", "107", "5", "Indirect", 40000.0),
    ("12B00001", "Husky Injection Mold. Syst S.A.-Dafza", "999", "1", "Direct", 30000.0),
    ("12B00002", "UPS DAFZA - Indoor Plants - AMC", "999", "1", "Direct", 30000.0),
    ("12B00003", "Scientific Design Company - Indoor Plants - AMC", "999", "1", "Direct", 25000.0),
]

ws_worksites = wb["Worksites"]
for r in range(5, ws_worksites.max_row + 1):
    for c in range(1, ws_worksites.max_column + 1):
        ws_worksites.cell(row=r, column=c).value = None

# Columns in Worksites:
# 1: #
# 2: job_number
# 3: job_name
# 4: renewal_reference
# 5: group_code
# 6: zone_code
# 7: customer_type
# 8: country
# 9: is_outdoor
# 10: contract_start_date
# 11: contract_end_date
# 12: labour_budget_amount
# 13: notes

for idx, (job_num, job_name, grp, zn, cust_type, budget) in enumerate(worksites_raw, start=5):
    is_outdoor = "Y" if job_num[2] == "A" else "N"
    ws_worksites.cell(row=idx, column=1, value=None)
    ws_worksites.cell(row=idx, column=2, value=job_num)
    ws_worksites.cell(row=idx, column=3, value=job_name)
    ws_worksites.cell(row=idx, column=4, value="R1")
    ws_worksites.cell(row=idx, column=5, value=grp)
    ws_worksites.cell(row=idx, column=6, value=zn)
    ws_worksites.cell(row=idx, column=7, value=cust_type)
    ws_worksites.cell(row=idx, column=8, value="AE")
    ws_worksites.cell(row=idx, column=9, value=is_outdoor)
    ws_worksites.cell(row=idx, column=10, value="2026-01-01")
    ws_worksites.cell(row=idx, column=11, value="2026-12-31")
    ws_worksites.cell(row=idx, column=12, value=budget)
    ws_worksites.cell(row=idx, column=13, value="Imported contract AMC 2026")

# 4. Job_Items Sheet
# Columns in Job_Items:
# 1: #
# 2: job_number
# 3: sub_item_code
# 4: staff_grade_description
# 5: planned_grade_code
# 6: deployment_type
# 7: frequency_unit
# 8: occurrences_per_period
# 9: period_interval
# 10: weekday_pattern
# 11: required_staff_count
# 12: hours_per_occurrence_per_staff
# 13: break_override_minutes
# 14: start_date
# 15: end_date
# 16: notes

ws_items = wb["Job_Items"]
for r in range(5, ws_items.max_row + 1):
    for c in range(1, ws_items.max_column + 1):
        ws_items.cell(row=r, column=c).value = None

current_item_row = 5
item_seq = 1

for job_num, _, _, _, _, _ in worksites_raw:
    letter = job_num[2]
    if letter == "A":
        # Outdoor job items
        items = [
            ("A", "Gardener - Hand Watering", "G1C", "PERMANENT", "WEEK", 6, 1, 3, 9.0, 30),
            ("B", "Gardener Helper", "G1C", "PERMANENT", "WEEK", 6, 1, 2, 9.0, 30),
            ("C", "Gardener Expert", "G1C", "PERMANENT", "WEEK", 6, 1, 1, 9.0, 30),
            ("D", "Irrigation Technician", "G1C", "PERMANENT", "MONTH", 1, 1, 1, 8.0, 30),
            ("F", "Team Leader", "G1C", "PERMANENT", "WEEK", 6, 1, 1, 9.0, 30),
            ("I", "Supervisor", "G1C", "REMOTE", "WEEK", 1, 1, 1, 8.0, 30),
        ]
    elif letter == "B":
        # Indoor job items
        items = [
            ("A", "Gardener Helper", "G1C", "PERMANENT", "WEEK", 3, 1, 1, 4.0, None),
            ("B", "Gardener Expert", "G1C", "PERMANENT", "WEEK", 2, 1, 1, 4.0, None),
            ("I", "Supervisor", "G1C", "REMOTE", "WEEK", 1, 1, 1, 2.0, None),
        ]
    else:
        # Water feature job items (C)
        items = [
            ("A", "Irrigation Technician", "G1C", "PERMANENT", "WEEK", 3, 1, 1, 4.0, 30),
            ("I", "Supervisor", "G1C", "REMOTE", "WEEK", 1, 1, 1, 2.0, None),
        ]

    for sub_code, sgd, grade, deploy, freq_u, occs, interval, staff_cnt, hrs, brk in items:
        ws_items.cell(row=current_item_row, column=1, value=None)
        ws_items.cell(row=current_item_row, column=2, value=job_num)
        ws_items.cell(row=current_item_row, column=3, value=sub_code)
        ws_items.cell(row=current_item_row, column=4, value=sgd)
        ws_items.cell(row=current_item_row, column=5, value=grade)
        ws_items.cell(row=current_item_row, column=6, value=deploy)
        ws_items.cell(row=current_item_row, column=7, value=freq_u)
        ws_items.cell(row=current_item_row, column=8, value=occs)
        ws_items.cell(row=current_item_row, column=9, value=interval)
        ws_items.cell(row=current_item_row, column=10, value=None)
        ws_items.cell(row=current_item_row, column=11, value=staff_cnt)
        ws_items.cell(row=current_item_row, column=12, value=hrs)
        ws_items.cell(row=current_item_row, column=13, value=brk)
        ws_items.cell(row=current_item_row, column=14, value="2026-01-01")
        ws_items.cell(row=current_item_row, column=15, value="2026-12-31")
        ws_items.cell(row=current_item_row, column=16, value=f"{sgd} maintenance schedule")
        current_item_row += 1
        item_seq += 1

wb.save(TEMPLATE_PATH)
print(f"Successfully populated {len(worksites_raw)} worksites and {item_seq - 1} job items into {TEMPLATE_PATH}")
