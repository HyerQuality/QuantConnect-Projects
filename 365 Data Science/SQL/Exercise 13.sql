CREATE TABLE departments_dup 
(
	dept_no CHAR(4),
    dept_name VARCHAR(255)
);

INSERT INTO 
	departments_dup
SELECT
	dept_no, dept_name
FROM 
	departments;
    
SELECT
	*
FROM
	departments_dup;