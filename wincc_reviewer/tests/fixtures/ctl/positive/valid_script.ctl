// WinCC OA Valid CTL Script (Positive)
void cbTemp(string dp, anytype val)
{
    // Temperature callback handler
    int err = getLastError();
    if(err!=0) { /* handle error */ }
}

void main()
{
    dpConnect("cbTemp", "System1:Tank1.Temp");
}

void onClose()
{
    dpDisconnect("cbTemp", "System1:Tank1.Temp");
}

