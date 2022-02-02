SELECT
	*
FROM
	departments;
    
DELETE FROM employees
WHERE
	emp_no = 999903;
    
ROLLBACK;

DELETE FROM departments
WHERE dept_no = "d010";
