SELECT
	*
FROM
	employees
ORDER BY emp_no DESC
LIMIT
	10;
INSERT INTO employees
(
	emp_no,
    birth_date,
    first_name,
    last_name,
    gender,
    hire_date
) Values
(
	999901,
    '1986-04-21',
    'John',
    'Smith',
    'M',
    '2011-01-01'
);