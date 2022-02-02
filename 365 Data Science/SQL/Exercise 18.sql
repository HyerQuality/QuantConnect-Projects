SELECT 
    m.emp_no, m.dept_no, e.first_name, e.last_name, e.hire_date
FROM
    dept_manager m
        INNER JOIN
    employees e ON m.emp_no = e.emp_no
GROUP BY m.emp_no;
