SELECT
	e.first_name, e.last_name
FROM
	employees e
WHERE
	e.emp_no IN
(
	SELECT
		dm.emp_no
	FROM
		dept_manager dm
);

SELECT
	e.emp_no, e.first_name, e.last_name
FROM
	employees e
INNER JOIN
	dept_manager dm ON e.emp_no = dm.emp_no
GROUP BY
	e.emp_no
ORDER BY
	e.emp_no ASC;