#Left Join
SELECT
	m.dept_no, m.emp_no, d.dept_name
FROM
	dept_manager_dup m
LEFT JOIN
	departments_dup d ON m.dept_no = d.dept_no
GROUP BY
	m.emp_no
ORDER BY
	m.emp_no ASC;
    