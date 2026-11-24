# Import template (v1.0)

`FieldWorkerTracker_Import_Template_v1.0.xlsx` is the workbook the client fills in: 15 data tabs (header row 4, data from row 5, grey EXAMPLE rows with fictional or sample values), plus README, Lists, SGD_Aliases and Field_Dictionary (every column, its rule and the client file column it comes from).

Tabs: Groups, Zones, Accommodations, Employees, Employee_Reporting, Employee_Salary, Worksites, Job_Items, Worksite_Supervisors (who sees which worksite, DEC-57), Leave (optional; read since v1.22.0, optional `status` APPROVED or PENDING at the end, blank = APPROVED), Public_Holidays (optional), Salary_Revisions and Salary_Revision_Lines (job budget only; optional `telephone_allowance` and `housing_transport_allowance` at the end of the lines sheet, blank = 0), Company_Settings, Time_Rules.

Cell rules (also on the workbook README and the import preview): a **blank cell keeps the existing value**; **`_` clears** a value; nothing is ever deleted by an import; the import shows new / updated (old -> new) / unchanged / clashes and changes nothing until confirmed. `Worksites` and `Accommodations` include an optional `boundary_polygon` column (accepting GeoJSON Polygon or WKT `POLYGON((lng lat, ...))`). You may upload either the full workbook, a single-sheet workbook with matching sheet name, or select specific sheet(s) directly on the Imports screen.

- The importer contract is `docs/11-import-pipeline.md`; the screens are in `docs/design/D6-import-and-setup.md`.
- In the final system the template is **generated from the importer's sheet registry** so they cannot drift; use the `import-column` skill when changing columns, and bump the file name version.
- Do not commit the client's original files (names, salaries). Examples use values taken from their files for realism; replace with fictional data for seed files.

**Staff types, grade codes and group codes (DEC-60).** The Lists sheet of a downloaded template carries the current lists (`staff_grade_description`, `grade_code`). An unknown staff type is an import error: an Admin adds it first in Settings → Managed Lists. A grade code on Employees or Job_Items must have a line in an active salary revision, in the database or in the same file's Salary_Revision_Lines; otherwise it is an error. A new group's code must be 3 digits.
