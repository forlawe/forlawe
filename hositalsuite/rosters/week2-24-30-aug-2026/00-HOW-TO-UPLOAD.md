# Week 2 roster — Mon 24 Aug to Sun 30 Aug 2026

Voice reminders stay on after you sign in.

These files match the Roster upload screen: columns **Name, Date, End Date, Shift, Leave Type, Section, Unit, Note**. Dates are `2026-08-24` through `2026-08-30`. Shifts are **DAY** (07:00–19:00) or **NIGHT** (19:00–07:00). Off days are **OFF** so nobody is put on duty by mistake.

The app only accepts names that already have an **active, approved** staff account. That is why there is a staff file first.

## What is in the pack

| File | Who | Pattern |
|------|-----|---------|
| `00-staff-accounts-upload-FIRST.csv` | Every name used below (98 people) | Create accounts first |
| `01-reception.csv` | 6 clerks | 2 day + 2 night, all week |
| `02-triage.csv` | 6 nurses | 2 day + 2 night, all week |
| `03-billing.csv` | 6 officers | 2 day + 2 night, all week |
| `04-megalex.csv` | 6 pay-point officers | 2 day + 2 night, all week |
| `05-lahsma.csv` | 6 LAHSMA officers | 2 day + 2 night, all week |
| `06-emergency.csv` | 4 nurses + 2 doctors | 2 day + 2 night, all week |
| `07-opd-doctors.csv` | 4 doctors | Day Mon–Fri, off weekend |
| `08-sopd.csv` | 2 surgeons | Day Mon–Fri |
| `09-mopd.csv` | 2 physicians | Day Mon–Fri |
| `10-dental.csv` | 2 dentists | Day Mon–Fri |
| `11-anc.csv` | 6 midwives / nurses | 2 day + 2 night |
| `12-og.csv` | 2 O&G doctors | Day Mon–Fri |
| `13-eye.csv` | 2 eye doctors | Day Mon–Fri |
| `14-paeds.csv` | 2 paediatricians | Day Mon–Fri |
| `15-physio.csv` | 2 physiotherapists | Day Mon–Fri |
| `16-mssd.csv` | 2 welfare officers | Day Mon–Fri |
| `17-male-medical-ward.csv` | 6 nurses | 2 day + 2 night |
| `18-female-medical-ward.csv` | 6 nurses | 2 day + 2 night |
| `19-male-surgical-ward.csv` | 6 nurses | 2 day + 2 night |
| `20-female-surgical-ward.csv` | 6 nurses | 2 day + 2 night |
| `21-maternity-ward.csv` | 6 midwives / nurses | 2 day + 2 night |
| `22-childrens-ward.csv` | 6 nurses | 2 day + 2 night |
| `WEEK2-ALL-ROSTERS.xlsx` | Everything, colour coded | For reading only — do not upload this book |

## Click by click

1. Sign in as Super Admin.
2. **Admin → Users → Bulk upload.** Choose `00-staff-accounts-upload-FIRST.csv`. Read the preview. Confirm.
3. **Admin → Users.** Approve every new person. Until you approve them they cannot appear on the roster.
4. **Admin → Structure.** For each department you will upload into, set the roster pattern to **Two 12-hour shifts (day / night)**. Billing, Megalex, Reception and Admin are often left on “Office hours” — that will turn every DAY/NIGHT line red.
5. Open **Roster**.
6. Pick the department that matches the file (table below).
7. Upload that one CSV. Read the preview. Every line should be green. Confirm.
8. Do the next CSV.

| Upload this | Under this department |
|-------------|------------------------|
| Reception / LAHSMA / MSSD | Administration & Human Resources |
| Triage / Emergency | Accident & Emergency |
| Billing / Megalex | Finance & Accounts |
| OPD doctors | Family Medicine / General Outpatient |
| SOPD / male surgical / female surgical | Surgery |
| MOPD / male medical / female medical | Internal Medicine |
| Dental | Dental Services |
| ANC / O&G / maternity ward | Obstetrics & Gynaecology |
| Eye | Ophthalmology (Eye Clinic) |
| Paediatrics / children ward | Paediatrics |
| Physio | Physiotherapy |

## If you already have these staff

Skip the staff file. Open the CSV and change the **Name** column so it matches your register **exactly** (same spelling, same title). Then upload.

## If a line is red

| Message | What to do |
|---------|------------|
| No active staff account matches | Create or approve that person, or fix the spelling |
| Already rostered | That person is already on that shift that day — leave it |
| Not used by this roster pattern | Department is still on office hours. Change it to “Two 12-hour shifts” first |

## Cover at a glance

- Front desks (Reception, Triage, Billing, Megalex, LAHSMA): **2 on days, 2 on nights**, every day. Each person has 2 or 3 offs in the week.
- Wards and A&E: same pattern.
- Clinic doctors, physio and MSSD: **2 on days Monday–Friday**, weekend off.

This is a starter week you can edit. It is not an EMR and it does not record diagnoses.
