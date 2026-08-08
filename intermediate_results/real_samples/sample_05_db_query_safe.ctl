void execute_safe_db()
{
  string sql = "SELECT user_id, role FROM users WHERE active = 1";
  dbExecuteQuery(sql);
}
