SELECT
	*
FROM
	employees
WHERE
	hire_date > '2000-01-01';

DROP INDEX i_hire_date ON employees;
CREATE INDEX i_hire_date ON employees (hire_date);

SELECT
	*
FROM
	employees
WHERE
	first_name = 'Georgi'
    AND last_name = 'Facello';

CREATE INDEX i_composite ON employees(first_name, last_name);

SHOW INDEX FROM employees FROM employees;

SELECT
	*
FROM
	salaries
WHERE
	salary > 89000
ORDER BY
	salary;
    
CREATE INDEX i_salary ON salaries(salary);