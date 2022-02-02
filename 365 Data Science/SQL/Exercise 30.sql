CREATE OR REPLACE VIEW v_Average_Manager_Salary AS
SELECT
	 ROUND(AVG(s.salary),2)
FROM
    salaries s
JOIN
	dept_manager dm ON s.emp_no = dm.emp_no;