import sqlparse

CASES = ["( AS )", "()", "( )", "(", ")", "(AS)", "( , )", "( SELECT )", "((  ))", "(a)", "( a )", "SELECT ( 1 )",
         "SELECT a FROM t WHERE ( a = 1 )", "INSERT INTO t VALUES ( 1, 2 )", "SELECT  (   a  +  b  )  FROM t",
         "( AS", "AS )", "(( AS ))", "( ( ) )", "f(  )", "SELECT  foo( a ,  b )"]
for sql in CASES:
    try:
        print(repr(sql), "->", repr(sqlparse.format(sql, strip_whitespace=True)))
    except Exception as e:
        print(repr(sql), "-> RAISES", type(e).__name__, e)
