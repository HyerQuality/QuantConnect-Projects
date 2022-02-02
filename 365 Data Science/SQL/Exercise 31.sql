DROP PROCEDURE IF EXISTS employees.average_salary;

Delimiter $$
CREATE PROCEDURE average_salary()
BEGIN
	SELECT
		AVG(salary)
	FROM
		salaries;
END$$
DELIMITER ;

CALL employees.average_salary();
