UPDATE departments dept_no
SET 
    dept_name = 'Data Analyst'
WHERE
    dept_name = 'Business Analyst';
    
SELECT
	*
FROM
	departments
ORDER BY
	dept_no;