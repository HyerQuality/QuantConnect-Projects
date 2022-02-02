SELECT
	dept_no,
    dept_name,
    COALESCE(dept_no, dept_name) as 'Dept_Info'
FROM
	departments_dup;