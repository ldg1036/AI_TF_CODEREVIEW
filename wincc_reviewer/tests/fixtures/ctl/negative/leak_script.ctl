// WinCC OA Violation CTL Script (Negative: Missing dpDisconnect)
void main()
{
    dpConnect("cbTemp", "System1:Tank1.Temp");
}
