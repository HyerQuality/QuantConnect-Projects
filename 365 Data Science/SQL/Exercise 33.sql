SET @v_emp_no = 0;
CALL employees.employee_id('Aruna', 'Journel', @v_emp_no);
SELECT @v_emp_no;