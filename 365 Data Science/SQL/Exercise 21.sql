SELECT
	dm.emp_no, e.emp_no, e.first_name, e.last_name, dm.dept_no, e.hire_date
FROM
	dept_manager dm, employees e
WHERE
	dm.emp_no = e.emp_no;
    
SELECT
	e.emp_no, e.first_name, e.last_name, e.hire_date, dm.emp_no, dm.dept_no
FROM
	employees e
INNER JOIN
	dept_manager dm ON e.emp_no = dm.emp_no
GROUP BY
	e.emp_no
ORDER BY
	e.emp_no ASC;