SELECT
	emp_no, count(from_date) as Signing_Date
FROM
	dept_emp
WHERE
	from_date > "2000-01-01"
GROUP BY
	emp_no
HAVING
	count(from_date) > 1
ORDER BY
	emp_no ASC; 
