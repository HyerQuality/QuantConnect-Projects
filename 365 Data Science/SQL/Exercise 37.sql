SELECT
	e.emp_no,
    e.first_name,
    e.last_name,
    IF(e.emp_no = dm.emp_no , 'Manager' , 'Employee') AS Role
FROM
	employees e
LEFT JOIN
	dept_manager dm ON dm.emp_no = e.emp_no
WHERE
	e.emp_no > '109990'
GROUP BY
	e.emp_no
ORDER BY
	e.emp_no;

SELECT
	dm.emp_no,
    e.first_name,
    e.last_name,
    MAX(s.salary) - MIN(s.salary) AS Change_In_Salary,
    CASE s.salary
		WHEN MAX(s.salary) - MIN(s.salary) > 30000 THEN 'Salary increased by $30,000 or more'
        ELSE 'Salary change was less than $30,000'
	END AS Salary_Difference
FROM
	dept_manager dm
JOIN
	salaries s ON s.emp_no = dm.emp_no
JOIN
	employees e ON e.emp_no = dm.emp_no
GROUP BY
	dm.emp_no
ORDER BY
	dm.emp_no;

SELECT
	e.emp_no,
    e.first_name,
    e.last_name,
    CASE
		WHEN MAX(de.to_date) > SYSDATE() THEN 'Still employed'
        ELSE 'No longer employed'
	END AS Employment_Status
FROM
	employees e
JOIN
	dept_emp de ON de.emp_no = e.emp_no
GROUP BY
	e.emp_no
ORDER BY
	e.emp_no
LIMIT 100;