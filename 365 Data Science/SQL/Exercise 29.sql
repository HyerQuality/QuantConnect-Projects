DROP TABLE IF EXISTS emp_manager;
CREATE TABLE emp_manager
(
	emp_no INT(11) NOT NULL,
    dept_no CHAR(4) NULL,
    manager_no INT(11) NOT NULL
);

INSERT INTO emp_manager SELECT
	U.*
FROM
(SELECT 
    A.*
FROM
    (SELECT 
        e.emp_no,
            MIN(de.dept_no),
            (SELECT 
                    emp_no
                FROM
                    dept_manager dm
                WHERE
                    dm.emp_no = '110022') AS dept_manager
    FROM
        employees e
    JOIN dept_emp de ON e.emp_no = de.emp_no
    WHERE
        10000 <= e.emp_no AND e.emp_no <= 10020
    GROUP BY e.emp_no
    ORDER BY e.emp_no) AS A 
UNION SELECT 
    B.*
FROM
    (SELECT 
        e.emp_no,
            MIN(de.dept_no),
            (SELECT 
                    emp_no
                FROM
                    dept_manager dm
                WHERE
                    dm.emp_no = '110039') AS dept_manager
    FROM
        employees e
    JOIN dept_emp de ON e.emp_no = de.emp_no
    WHERE
        10021 <= e.emp_no AND e.emp_no <= 10040
    GROUP BY e.emp_no
    ORDER BY e.emp_no) AS B 
UNION SELECT 
    C.*
FROM
    (SELECT 
        e.emp_no,
            MIN(de.dept_no),
            (SELECT 
                    emp_no
                FROM
                    dept_manager dm
                WHERE
                    dm.emp_no = '110039') AS dept_manager
    FROM
        employees e
    JOIN dept_emp de ON e.emp_no = de.emp_no
    WHERE
        e.emp_no = 110022
    GROUP BY e.emp_no
    ORDER BY e.emp_no) AS C 
UNION SELECT 
    D.*
FROM
    (SELECT 
        e.emp_no,
            MIN(de.dept_no),
            (SELECT 
                    emp_no
                FROM
                    dept_manager dm
                WHERE
                    dm.emp_no = '110022') AS dept_manager
    FROM
        employees e
    JOIN dept_emp de ON e.emp_no = de.emp_no
    WHERE
        e.emp_no = 110039
    GROUP BY e.emp_no
    ORDER BY e.emp_no) AS D) AS U;