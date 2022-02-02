SELECT 
	e.emp_no, e.last_name, dm.emp_no, dm.dept_no
FROM
	employees e
LEFT JOIN
	dept_manager dm ON e.emp_no = dm.emp_no
WHERE
	e.last_name = 'Markovitch'
GROUP BY
	e.emp_no
ORDER BY
	dm.dept_no DESC, e.emp_no;
