DROP PROCEDURE IF EXISTS employee_id;
DELIMITER $$
CREATE PROCEDURE employee_id(IN first_name VARCHAR(256), IN last_name VARCHAR(256))
BEGIN
	SELECT
		e.emp_no
	FROM
		employees e
	WHERE
		e.first_name = first_name AND e.last_name = last_name;
END$$
DELIMITER ;employee_id