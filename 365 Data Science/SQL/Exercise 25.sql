SELECT
	e.gender, count(e.gender) AS Gender_Count
FROM
	employees e
JOIN
	dept_manager dm ON e.emp_no = dm.emp_no
GROUP BY
	e.gender
ORDER BY
	e.gender ASC;