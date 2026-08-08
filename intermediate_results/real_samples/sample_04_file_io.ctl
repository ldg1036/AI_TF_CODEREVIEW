void write_log() { int f = fopen("C:\\log.txt", "a"); if(f>0) { fputs("event\n", f); fclose(f); } }
