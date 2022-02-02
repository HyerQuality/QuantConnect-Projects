DROP TABLE IF EXISTS departments_dup;
CREATE TABLE departments_dup
(
	dept_no CHAR(4) NULL,
    dept_name VARCHAR(40) NULL
);

INSERT INTO departments_dup
SELECT
	dept_no, dept_name
FROM
	departments;

INSERT INTO departments_dup
(
	dept_name
)
Values
(
	'Public Relations'
);


INSERT INTO departments_dup
(
	dept_no
)
VALUES
	("d010"),
	("d011");

SET SQL_SAFE_UPDATES = 0;    
DELETE FROM departments_dup WHERE dept_no='d002';
SET SQL_SAFE_UPDATES = 1;

SELECT
	*
FROM
	departments_dup
ORDER BY
	dept_no ASC;