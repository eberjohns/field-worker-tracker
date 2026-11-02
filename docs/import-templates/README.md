# Import template (v1.0)

`FieldWorkerTracker_Import_Template_v1.0.xlsx` is the workbook the client fills in: 14 data tabs (header row 4, data from row 5, grey EXAMPLE rows with fictional or sample values), plus README, Lists, SGD_Aliases and Field_Dictionary (every column, its rule and the client file column it comes from).

Tabs: Groups, Zones, Accommodations, Employees, Employee_Reporting, Employee_Salary, Worksites, Job_Items, Leave (optional), Public_Holidays (optional), Salary_Revisions and Salary_Revision_Lines (job budget only), Company_Settings, Time_Rules.

Cell rules (also on the workbook README and the import preview): a **blank cell keeps the existing value**; **`_` clears** a value; nothing is ever deleted by an import; the import shows new / updated (old -> new) / unchanged / clashes and changes nothing until confirmed.

- The importer contract is `docs/11-import-pipeline.md`; the screens are in `docs/design/D6-import-and-setup.md`.
- In the final system the template is **generated from the importer's sheet registry** so they cannot drift; use the `import-column` skill when changing columns, and bump the file name version.
- Do not commit the client's original files (names, salaries). Examples use values taken from their files for realism; replace with fictional data for seed files.
