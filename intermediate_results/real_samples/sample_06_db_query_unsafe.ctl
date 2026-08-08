void execute_unsafe_db(string input_val)
{
  string sql = "SELECT * FROM logs WHERE user = '" + input_val + "'";
  dbExecuteQuery(sql);
}
