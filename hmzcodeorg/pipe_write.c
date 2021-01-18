
#include <stdio.h> 
#include <stdlib.h> 
#include <string.h> 
#include <stdint.h> 
#include <math.h> 
#include <fcntl.h> 
#include <sys/stat.h> 
#include <sys/types.h> 
#include <unistd.h> 
#include <errno.h> 

#define HEADER_LEN 14

static int CHUNK = 32 * 16 * 2;
int main (int argc, char **argv)
{

    if (argc != 3)
    {
        printf ("USAGE : %s <wav file - mono-16khz-S16LE> <audio pipe>\n", argv[0]);
        return 1;
    }

    static int fd;
    static int ft = 1;
    char *myfifo = argv[2];
    uint8_t *buf = (uint8_t*)malloc (CHUNK+8+2+4);
    uint64_t start_pts = 0;//pow(2,63)/1000000;

    buf[0] = 0xc0;
    buf[1] = 0xff;
    buf[2] = 0xee;
    buf[3] = 0xee;


    buf[4] = start_pts;
    buf[5] = start_pts >> 8;
    buf[6] = start_pts >> 16;
    buf[7] = start_pts >> 24;
    buf[8] = start_pts >> 32;
    buf[9] = start_pts >> 40;
    buf[10] = start_pts >> 48;
    buf[11] = start_pts >> 56;

    buf[12] = CHUNK;
    buf[13] = CHUNK >> 8;

    FILE *fp = fopen(argv[1], "rb");

    if (ft)
    {
        //remove (myfifo);
        mkfifo(myfifo, 0666);
        printf ("%s  errno:%d\n", __func__,  (errno));
        //perror(errno);
        fd = open(myfifo, O_WRONLY );
        printf ("%s fd:%d errno:%d\n", __func__,  fd, (errno));
       // perror(errno);
        ft = 0;

    }

    uint64_t pts = start_pts;
    while (fread (buf+HEADER_LEN, 1, CHUNK, fp) == CHUNK)
    {
        buf[4] = pts;
        buf[5] = pts >> 8;
        buf[6] = pts >> 16;
        buf[7] = pts >> 24;
        buf[8] = pts >> 32;
        buf[9] = start_pts >> 40;
        buf[10] = start_pts >> 48;
        buf[11] = start_pts >> 56;
        int ret = write(fd, buf, CHUNK+HEADER_LEN); 
        pts += 32;
        //usleep (10000);
        //printf ("%s write  errno:%d\n", __func__,  (errno));
    }
}
