SELECT
	e.first_name, e.last_name, e.hire_date, t.title, dm.from_date, d.dept_name
FROM
	employees e
JOIN
	dept_manager dm ON e.emp_no = dm.emp_no
JOIN
	titles t ON e.emp_no = t.emp_no
JOIN
	departments d ON d.dept_no = dm.dept_no
WHERE
	t.title = 'Manager'
ORDER BY
	e.emp_no ASC;