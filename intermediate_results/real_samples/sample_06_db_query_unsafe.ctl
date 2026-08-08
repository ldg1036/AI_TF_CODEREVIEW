void unsafe_db(string input_val) { string s = "SELECT * FROM users WHERE name='" + input_val + "'"; dbExecuteQuery(s); }
