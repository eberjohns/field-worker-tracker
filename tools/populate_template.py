"""Populate the entire Master Data Import Template with complete, realistic, consistent data."""

from pathlib import Path
import openpyxl

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "docs/import-templates/FieldWorkerTracker_Import_Template_v1.0.xlsx"
wb = openpyxl.load_workbook(TEMPLATE_PATH)

def clear_data_rows(sheet_name: str):
    ws = wb[sheet_name]
    for r in range(5, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            ws.cell(row=r, column=c).value = None
    return ws

# 1. Groups Sheet
ws_groups = clear_data_rows("Groups")
groups_data = [
    ("102", "Dr. Moopens (Aster)"),
    ("104", "Dubai Developments - DIRE"),
    ("106", "Al Futtaim Real Estate properties - AFRE"),
    ("107", "Unilever Gulf FZE - Indoor and Landscaping AMC"),
    ("999", "Miscellenious"),
]
for idx, (code, name) in enumerate(groups_data, start=5):
    ws_groups.cell(row=idx, column=1, value=None)
    ws_groups.cell(row=idx, column=2, value=code)
    ws_groups.cell(row=idx, column=3, value=name)

# 2. Zones Sheet
ws_zones = clear_data_rows("Zones")
zones_data = [
    ("1", "Al Qusais / Deira"),
    ("2", "Bur Dubai / Business Bay"),
    ("3", "Al Quoz / Jumeira upto 5th Interchange"),
    ("5", "Jebel Ali"),
]
for idx, (code, name) in enumerate(zones_data, start=5):
    ws_zones.cell(row=idx, column=1, value=None)
    ws_zones.cell(row=idx, column=2, value=code)
    ws_zones.cell(row=idx, column=3, value=name)

# 3. Accommodations Sheet
ws_acc = clear_data_rows("Accommodations")
accommodations_data = [
    ("ACC-01", "Sonapur Main Staff Camp", "Muhaisnah 2, Sonapur, Dubai", "AE", "Primary staff housing"),
    ("ACC-02", "Al Quoz Industrial Camp", "Al Quoz Industrial Area 3, Dubai", "AE", "Central zone team housing"),
    ("ACC-03", "Jebel Ali Staff Quarters", "JAFZA South Camp Complex, Dubai", "AE", "Jebel Ali / DIP crew quarters"),
    ("ACC-04", "DIP Workers Complex", "Dubai Investments Park 1, Dubai", "AE", "South zone facilities"),
]
for idx, (code, name, addr, country, notes) in enumerate(accommodations_data, start=5):
    ws_acc.cell(row=idx, column=1, value=None)
    ws_acc.cell(row=idx, column=2, value=code)
    ws_acc.cell(row=idx, column=3, value=name)
    ws_acc.cell(row=idx, column=4, value=addr)
    ws_acc.cell(row=idx, column=5, value=country)
    ws_acc.cell(row=idx, column=6, value=notes)

# 4. Employees Sheet
ws_emp = clear_data_rows("Employees")
employees_data = [
    # tally_id, name, role, grade_code, sgd, country, off_day, is_driver, acc_code, join, phone, email
    ("1001", "Ahmed Al-Mansoor", "ENGINEER", "G5A", "HSE Engineer", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001001", "ahmed.mansoor@example.com"),
    ("1002", "Rashid Tariq", "SUPERINTENDENT", "G4B", "Superintendent", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001002", "rashid.tariq@example.com"),
    ("1003", "Faisal Khan", "SUPERINTENDENT", "G4B", "Superintendent", "AE", "SUNDAY", "N", "ACC-03", "2024-01-01", "+971500001003", "faisal.khan@example.com"),
    ("1004", "Zaid Mahmoud", "SUPERVISOR", "G3B", "Supervisor", "AE", "SUNDAY", "N", "ACC-01", "2024-01-01", "+971500001004", "zaid.mahmoud@example.com"),
    ("1005", "Bilal Hassan", "SUPERVISOR", "G3B", "Supervisor", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001005", "bilal.hassan@example.com"),
    ("1006", "Tariq Aziz", "SUPERVISOR", "G3B", "Supervisor", "AE", "SUNDAY", "N", "ACC-03", "2024-01-01", "+971500001006", "tariq.aziz@example.com"),
    ("1007", "Ramesh Kumar", "WORKER", "G3B", "Team Leader", "AE", "SUNDAY", "N", "ACC-01", "2024-01-01", "+971500001007", None),
    ("1008", "Suresh Babu", "WORKER", "G3B", "Team Leader", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001008", None),
    ("1009", "Vikram Singh", "WORKER", "G3B", "Team Leader", "AE", "SUNDAY", "N", "ACC-03", "2024-01-01", "+971500001009", None),
    ("1010", "Manoj Patel", "WORKER", "G3B", "Irrigation Technician", "AE", "SUNDAY", "N", "ACC-01", "2024-01-01", "+971500001010", None),
    ("1011", "Deepak Sharma", "WORKER", "G3B", "Irrigation Technician", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001011", None),
    ("1012", "Dinesh Rao", "WORKER", "G3B", "Irrigation Technician", "AE", "SUNDAY", "N", "ACC-03", "2024-01-01", "+971500001012", None),
    ("1013", "Rajesh Nair", "WORKER", "G2B", "Gardener Expert", "AE", "SUNDAY", "N", "ACC-01", "2024-01-01", "+971500001013", None),
    ("1014", "Prakash Varma", "WORKER", "G2B", "Gardener Expert", "AE", "SUNDAY", "N", "ACC-02", "2024-01-01", "+971500001014", None),
    ("1015", "Anand Mohan", "WORKER", "G2B", "Gardener Expert", "AE", "SUNDAY", "N", "ACC-03", "2024-01-01", "+971500001015", None),
    ("1016", "Sunilkumar G", "WORKER", "G2B", "Gardener Expert", "AE", "SUNDAY", "N", "ACC-04", "2024-01-01", "+971500001016", None),
    ("1017", "Mohan Lal", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-01", "2024-01-01", "+971500001017", None),
    ("1018", "Raju Prasad", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-01", "2024-01-01", "+971500001018", None),
    ("1019", "Anil Yadav", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-02", "2024-01-01", "+971500001019", None),
    ("1020", "Mukesh Das", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-02", "2024-01-01", "+971500001020", None),
    ("1021", "Sanjay Gupta", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-03", "2024-01-01", "+971500001021", None),
    ("1022", "Gopal Krishna", "WORKER", "G1C", "Gardener Helper", "AE", "FRIDAY", "N", "ACC-03", "2024-01-01", "+971500001022", None),
    ("1023", "Santosh Kumar", "WORKER", "G1B", "Gardener - Hand Watering", "AE", "FRIDAY", "N", "ACC-01", "2024-01-01", "+971500001023", None),
    ("1024", "Jitender Pal", "WORKER", "G1B", "Gardener - Hand Watering", "AE", "FRIDAY", "Y", "ACC-02", "2024-01-01", "+971500001024", None),
    ("1025", "Prem Chand", "WORKER", "G1B", "Gardener - Hand Watering", "AE", "FRIDAY", "Y", "ACC-03", "2024-01-01", "+971500001025", None),
]

for idx, (tid, name, role, gr_code, sgd, ctry, off_day, is_drv, acc_c, join_d, phone, email) in enumerate(employees_data, start=5):
    # Create realistic variation in document expiry dates for testing Phase 09 document monitoring:
    # 1007: Visa expiring soon (Nov 20, 2026 - within 10 days)
    # 1010: Passport expiring soon (Dec 5, 2026 - within 25 days)
    # 1013: Emirates ID expired (Oct 15, 2026 - already expired)
    # 1017: Labour Card expiring soon (Nov 28, 2026 - within 18 days)
    # 1024: Driver's License expiring soon (Dec 2, 2026 - within 22 days)
    visa_exp = "2026-11-20" if tid == "1007" else "2027-12-31"
    passport_exp = "2026-12-05" if tid == "1010" else "2029-12-31"
    eid_exp = "2026-10-15" if tid == "1013" else "2027-12-31"
    labour_exp = "2026-11-28" if tid == "1017" else "2027-12-31"
    dl_exp = "2026-12-02" if tid == "1024" else ("2028-12-31" if is_drv == "Y" else None)

    ws_emp.cell(row=idx, column=1, value=None)
    ws_emp.cell(row=idx, column=2, value=tid)
    ws_emp.cell(row=idx, column=3, value=name)
    ws_emp.cell(row=idx, column=4, value=role)
    ws_emp.cell(row=idx, column=5, value=gr_code)
    ws_emp.cell(row=idx, column=6, value=sgd)
    ws_emp.cell(row=idx, column=7, value=ctry)
    ws_emp.cell(row=idx, column=8, value=off_day)
    ws_emp.cell(row=idx, column=9, value=is_drv)
    ws_emp.cell(row=idx, column=10, value=acc_c)
    ws_emp.cell(row=idx, column=11, value=join_d)
    ws_emp.cell(row=idx, column=12, value=None) # end date
    ws_emp.cell(row=idx, column=13, value=visa_exp) # visa
    ws_emp.cell(row=idx, column=14, value=passport_exp) # passport
    ws_emp.cell(row=idx, column=15, value=eid_exp) # eid
    ws_emp.cell(row=idx, column=16, value=labour_exp) # labour card
    ws_emp.cell(row=idx, column=17, value=dl_exp) # dl
    ws_emp.cell(row=idx, column=18, value=phone)
    ws_emp.cell(row=idx, column=19, value=email)
    ws_emp.cell(row=idx, column=20, value="Active personnel")

# 5. Employee_Reporting Sheet
ws_rep = clear_data_rows("Employee_Reporting")
reporting_data = [
    ("1004", "1002", "SUPERINTENDENT"),
    ("1004", "1001", "ENGINEER"),
    ("1005", "1002", "SUPERINTENDENT"),
    ("1005", "1001", "ENGINEER"),
    ("1006", "1003", "SUPERINTENDENT"),
    ("1006", "1001", "ENGINEER"),
    # Workers under Zaid (1004)
    ("1007", "1004", "SUPERVISOR"),
    ("1010", "1004", "SUPERVISOR"),
    ("1013", "1004", "SUPERVISOR"),
    ("1017", "1004", "SUPERVISOR"),
    ("1018", "1004", "SUPERVISOR"),
    ("1023", "1004", "SUPERVISOR"),
    # Workers under Bilal (1005)
    ("1008", "1005", "SUPERVISOR"),
    ("1011", "1005", "SUPERVISOR"),
    ("1014", "1005", "SUPERVISOR"),
    ("1019", "1005", "SUPERVISOR"),
    ("1020", "1005", "SUPERVISOR"),
    ("1024", "1005", "SUPERVISOR"),
    # Workers under Tariq (1006)
    ("1009", "1006", "SUPERVISOR"),
    ("1012", "1006", "SUPERVISOR"),
    ("1015", "1006", "SUPERVISOR"),
    ("1016", "1006", "SUPERVISOR"),
    ("1021", "1006", "SUPERVISOR"),
    ("1022", "1006", "SUPERVISOR"),
    ("1025", "1006", "SUPERVISOR"),
]
for idx, (emp_id, mgr_id, rel) in enumerate(reporting_data, start=5):
    ws_rep.cell(row=idx, column=1, value=None)
    ws_rep.cell(row=idx, column=2, value=emp_id)
    ws_rep.cell(row=idx, column=3, value=mgr_id)
    ws_rep.cell(row=idx, column=4, value=rel)
    ws_rep.cell(row=idx, column=5, value="Primary operations link")

# 6. Employee_Salary Sheet
ws_sal = clear_data_rows("Employee_Salary")
salary_map = {
    "1001": (6500.0, 1000.0, 0.0, 800.0),
    "1002": (4800.0, 700.0, 0.0, 500.0),
    "1003": (4800.0, 700.0, 0.0, 500.0),
    "1004": (3200.0, 400.0, 150.0, 0.0),
    "1005": (3200.0, 400.0, 150.0, 0.0),
    "1006": (3200.0, 400.0, 150.0, 0.0),
    "1007": (2200.0, 250.0, 0.0, 0.0),
    "1008": (2200.0, 250.0, 0.0, 0.0),
    "1009": (2200.0, 250.0, 0.0, 0.0),
    "1010": (1800.0, 200.0, 0.0, 0.0),
    "1011": (1800.0, 200.0, 0.0, 0.0),
    "1012": (1800.0, 200.0, 0.0, 0.0),
    "1013": (1800.0, 200.0, 0.0, 0.0),
    "1014": (1800.0, 200.0, 0.0, 0.0),
    "1015": (1800.0, 200.0, 0.0, 0.0),
    "1016": (1800.0, 200.0, 0.0, 0.0),
    "1017": (1200.0, 150.0, 0.0, 0.0),
    "1018": (1200.0, 150.0, 0.0, 0.0),
    "1019": (1200.0, 150.0, 0.0, 0.0),
    "1020": (1200.0, 150.0, 0.0, 0.0),
    "1021": (1200.0, 150.0, 0.0, 0.0),
    "1022": (1200.0, 150.0, 0.0, 0.0),
    "1023": (1300.0, 150.0, 0.0, 0.0),
    "1024": (1400.0, 200.0, 0.0, 0.0), # Driver
    "1025": (1400.0, 200.0, 0.0, 0.0), # Driver
}

for idx, (emp_id, (basic, special, phone_al, house_tr)) in enumerate(salary_map.items(), start=5):
    ws_sal.cell(row=idx, column=1, value=None)
    ws_sal.cell(row=idx, column=2, value=emp_id)
    ws_sal.cell(row=idx, column=3, value="2026-01-01")
    ws_sal.cell(row=idx, column=4, value=8.0)
    ws_sal.cell(row=idx, column=5, value=basic)
    ws_sal.cell(row=idx, column=6, value=special)
    ws_sal.cell(row=idx, column=7, value=0.0)
    ws_sal.cell(row=idx, column=8, value=0.0)
    ws_sal.cell(row=idx, column=9, value=phone_al)
    ws_sal.cell(row=idx, column=10, value=house_tr)
    ws_sal.cell(row=idx, column=11, value="Annual wage structure 2026")

# 7. Worksites Sheet
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

ws_worksites = clear_data_rows("Worksites")
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

# 8. Job_Items Sheet
ws_items = clear_data_rows("Job_Items")
current_item_row = 5

for job_num, _, _, _, _, _ in worksites_raw:
    letter = job_num[2]
    if letter == "A":
        items = [
            ("A", "Gardener - Hand Watering", "G1C", "PERMANENT", "WEEK", 6, 1, 3, 9.0, 30),
            ("B", "Gardener Helper", "G1C", "PERMANENT", "WEEK", 6, 1, 2, 9.0, 30),
            ("C", "Gardener Expert", "G1C", "PERMANENT", "WEEK", 6, 1, 1, 9.0, 30),
            ("D", "Irrigation Technician", "G1C", "PERMANENT", "MONTH", 1, 1, 1, 8.0, 30),
            ("F", "Team Leader", "G1C", "PERMANENT", "WEEK", 6, 1, 1, 9.0, 30),
            ("I", "Supervisor", "G1C", "REMOTE", "WEEK", 1, 1, 1, 8.0, 30),
        ]
    elif letter == "B":
        items = [
            ("A", "Gardener Helper", "G1C", "PERMANENT", "WEEK", 3, 1, 1, 4.0, None),
            ("B", "Gardener Expert", "G1C", "PERMANENT", "WEEK", 2, 1, 1, 4.0, None),
            ("I", "Supervisor", "G1C", "REMOTE", "WEEK", 1, 1, 1, 2.0, None),
        ]
    else:
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
        ws_items.cell(row=current_item_row, column=16, value=f"{sgd} schedule")
        current_item_row += 1

# 9. Public_Holidays Sheet
ws_hol = clear_data_rows("Public_Holidays")
holidays_data = [
    ("2026-01-01", "New Year's Day", "AE", "Official Public Holiday"),
    ("2026-03-20", "Eid Al Fitr (Day 1)", "AE", "Islamic Holiday"),
    ("2026-03-21", "Eid Al Fitr (Day 2)", "AE", "Islamic Holiday"),
    ("2026-03-22", "Eid Al Fitr (Day 3)", "AE", "Islamic Holiday"),
    ("2026-05-27", "Arafat Day", "AE", "Islamic Holiday"),
    ("2026-05-28", "Eid Al Adha (Day 1)", "AE", "Islamic Holiday"),
    ("2026-05-29", "Eid Al Adha (Day 2)", "AE", "Islamic Holiday"),
    ("2026-06-17", "Islamic New Year", "AE", "Hijri New Year"),
    ("2026-12-02", "UAE National Day", "AE", "National Day Holiday"),
    ("2026-12-03", "UAE National Day Holiday", "AE", "National Day Holiday"),
]
for idx, (dt, name, ctry, notes) in enumerate(holidays_data, start=5):
    ws_hol.cell(row=idx, column=1, value=None)
    ws_hol.cell(row=idx, column=2, value=dt)
    ws_hol.cell(row=idx, column=3, value=name)
    ws_hol.cell(row=idx, column=4, value=ctry)
    ws_hol.cell(row=idx, column=5, value=notes)

# 10. Company_Settings Sheet
ws_set = clear_data_rows("Company_Settings")
settings_data = [
    ("provision_visa", "250.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly visa provision per worker"),
    ("provision_air_ticket", "150.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly air ticket provision"),
    ("provision_uniform", "50.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly uniform allowance"),
    ("provision_medical", "120.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly medical insurance provision"),
    ("provision_accommodation", "300.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly camp accommodation allowance"),
    ("provision_transportation", "200.00", "AED", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Monthly staff transport provision"),
    ("standard_daily_hours", "8.0", "HOURS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Standard daily working hours"),
    ("default_password", "ChangeMe123!", "TEXT", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Default onboarding password"),
    ("default_password_max_days", "7", "DAYS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Max days to change default password before lock"),
    ("mobile_default_password", "Welcome123!", "TEXT", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Default password for mobile worker accounts"),
    ("day_plan_alarm_lead_minutes", "30", "MINUTES", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Alarm lead time in minutes before shift start"),
    ("day_plan_window_days_ahead", "30", "DAYS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Number of days ahead to sync day plans"),
    ("sync_retention_days", "30", "DAYS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Sync changes compaction retention days"),
    ("geofence_circle_radius_m", "300", "METERS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Hardware geofence perimeter radius buffer"),
    ("approach_polling_interval_s", "60", "SECONDS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Approach polling interval inside perimeter"),
    ("confirmation_polling_interval_s", "300", "SECONDS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Confirmation polling interval inside polygon"),
    ("live_active_window_minutes", "15", "MINUTES", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Active threshold window for live map tracking"),
    ("pending_visit_escalation_days", "3", "DAYS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Threshold days before open pending visit escalates"),
    ("doc_expiry_lead_days", "30", "DAYS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Lead days before document expiration to raise alert"),
    ("attendance_grace_minutes", "15", "MINUTES", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Grace window for late arrival without penalty"),
    ("attendance_break_minutes_default", "60", "MINUTES", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Default midday break duration"),
    ("overtime_daily_threshold_hours", "8.0", "HOURS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Daily standard hours before OT1 overtime accumulates"),
    ("overtime_daily_cap_hours", "2.0", "HOURS", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Maximum daily overtime cap"),
    ("travel_speed_min_kmh", "10.0", "KMH", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Minimum speed threshold to classify as transit"),
    ("travel_speed_max_kmh", "130.0", "KMH", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Maximum valid road travel speed"),
    ("budget_only_staff_types", '["HSE Engineer"]', "LIST", "AE", "2026-01-01", "GIVEN_BY_CLIENT", "Budget-only staff types excluded from phone scheduling"),
]
for idx, (key, val, unit, ctry, eff_from, status, desc) in enumerate(settings_data, start=5):
    ws_set.cell(row=idx, column=1, value=None)
    ws_set.cell(row=idx, column=2, value=key)
    ws_set.cell(row=idx, column=3, value=val)
    ws_set.cell(row=idx, column=4, value=unit)
    ws_set.cell(row=idx, column=5, value=ctry)
    ws_set.cell(row=idx, column=6, value=eff_from)
    ws_set.cell(row=idx, column=7, value=status)
    ws_set.cell(row=idx, column=8, value=desc)

# 11. Time_Rules Sheet
ws_time = clear_data_rows("Time_Rules")
ws_time.cell(row=5, column=1, value=None)
ws_time.cell(row=5, column=2, value="Standard Company Workday")
ws_time.cell(row=5, column=3, value="AE")
ws_time.cell(row=5, column=4, value="COMPANY")
ws_time.cell(row=5, column=5, value=None)
ws_time.cell(row=5, column=6, value="ALL")
ws_time.cell(row=5, column=7, value="2026-01-01")
ws_time.cell(row=5, column=8, value=None)
ws_time.cell(row=5, column=9, value="06:00")
ws_time.cell(row=5, column=10, value="07:00")
ws_time.cell(row=5, column=11, value=60)
ws_time.cell(row=5, column=12, value="16:00")
ws_time.cell(row=5, column=13, value="17:00")
ws_time.cell(row=5, column=14, value=0)
ws_time.cell(row=5, column=15, value="Standard company schedule and break window")

# 12. Leave Sheet
ws_leave = clear_data_rows("Leave")
leave_data = [
    ("1010", "ANNUAL", "2026-12-10", "2026-12-20", "Annual vacation travel"),
    ("1013", "SICK", "2026-11-20", "2026-11-22", "Medical sick leave with doctor certificate"),
    ("1017", "EMERGENCY", "2026-11-25", "2026-11-27", "Family emergency leave"),
]
for idx, (tid, l_type, f_date, t_date, reason) in enumerate(leave_data, start=5):
    ws_leave.cell(row=idx, column=1, value=None)
    ws_leave.cell(row=idx, column=2, value=tid)
    ws_leave.cell(row=idx, column=3, value=l_type)
    ws_leave.cell(row=idx, column=4, value=f_date)
    ws_leave.cell(row=idx, column=5, value=t_date)
    ws_leave.cell(row=idx, column=6, value=reason)

# 13. Salary_Revisions Sheet
ws_srev = clear_data_rows("Salary_Revisions")
revisions_data = [
    ("REV-2026", "2026 Budget Standard", "AE", "2026-01-01", "APPROVED", "Approved budget pricing structure"),
]
for idx, (code, name, ctry, eff_from, status, notes) in enumerate(revisions_data, start=5):
    ws_srev.cell(row=idx, column=1, value=None)
    ws_srev.cell(row=idx, column=2, value=code)
    ws_srev.cell(row=idx, column=3, value=name)
    ws_srev.cell(row=idx, column=4, value=ctry)
    ws_srev.cell(row=idx, column=5, value=eff_from)
    ws_srev.cell(row=idx, column=6, value=status)
    ws_srev.cell(row=idx, column=7, value=notes)

# 14. Salary_Revision_Lines Sheet
ws_srev_lines = clear_data_rows("Salary_Revision_Lines")
rev_lines = [
    ("REV-2026", "G1B", "Gardener - Hand Watering", 1300.0, 150.0, 0.0, 0.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G1B"),
    ("REV-2026", "G1C", "Gardener Helper", 1200.0, 150.0, 0.0, 0.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G1C"),
    ("REV-2026", "G2B", "Gardener Expert", 1800.0, 200.0, 0.0, 0.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G2B"),
    ("REV-2026", "G3B", "Team Leader / Supervisor", 2200.0, 250.0, 0.0, 0.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G3B"),
    ("REV-2026", "G4B", "Superintendent", 4800.0, 700.0, 0.0, 500.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G4B"),
    ("REV-2026", "G5A", "HSE Engineer", 6500.0, 1000.0, 0.0, 800.0, 250.0, 150.0, 50.0, 120.0, 300.0, 200.0, "Standard G5A"),
]
for idx, (rcode, gcode, gtitle, basic, special, fixed_ot, bonus, visa, ticket, uniform, medical, acc, trans, notes) in enumerate(rev_lines, start=5):
    ws_srev_lines.cell(row=idx, column=1, value=None)
    ws_srev_lines.cell(row=idx, column=2, value=rcode)
    ws_srev_lines.cell(row=idx, column=3, value=gcode)
    ws_srev_lines.cell(row=idx, column=4, value=gtitle)
    ws_srev_lines.cell(row=idx, column=5, value=basic)
    ws_srev_lines.cell(row=idx, column=6, value=special)
    ws_srev_lines.cell(row=idx, column=7, value=fixed_ot)
    ws_srev_lines.cell(row=idx, column=8, value=bonus)
    ws_srev_lines.cell(row=idx, column=9, value=visa)
    ws_srev_lines.cell(row=idx, column=10, value=ticket)
    ws_srev_lines.cell(row=idx, column=11, value=uniform)
    ws_srev_lines.cell(row=idx, column=12, value=medical)
    ws_srev_lines.cell(row=idx, column=13, value=acc)
    ws_srev_lines.cell(row=idx, column=14, value=trans)
    ws_srev_lines.cell(row=idx, column=15, value=notes)

wb.save(TEMPLATE_PATH)
print("Successfully populated all sheets in template:")
print(f"  - Groups: {len(groups_data)}")
print(f"  - Zones: {len(zones_data)}")
print(f"  - Accommodations: {len(accommodations_data)}")
print(f"  - Employees: {len(employees_data)}")
print(f"  - Employee_Reporting: {len(reporting_data)}")
print(f"  - Employee_Salary: {len(salary_map)}")
print(f"  - Worksites: {len(worksites_raw)}")
print(f"  - Job_Items: {current_item_row - 5}")
print(f"  - Leave: {len(leave_data)}")
print(f"  - Public_Holidays: {len(holidays_data)}")
print(f"  - Salary_Revisions: {len(revisions_data)}")
print(f"  - Salary_Revision_Lines: {len(rev_lines)}")
print(f"  - Company_Settings: {len(settings_data)}")
print(f"  - Time_Rules: 1")
