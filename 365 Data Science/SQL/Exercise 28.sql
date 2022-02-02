SELECT 
    *
FROM
    dept_manager
WHERE
    emp_no IN (SELECT 
            emp_no
        FROM
            employees
        WHERE
            hire_date BETWEEN '1990-01-01' AND '1995-01-01');
            
SELECT
	*
FROM
	employees e
WHERE
	EXISTS(
		SELECT
			*
		FROM
			titles t
		WHERE
			e.emp_no = t.emp_no AND t.title = 'Assistant Engineer');
	

	