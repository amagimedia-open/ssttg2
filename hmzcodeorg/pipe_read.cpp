#include <stdio.h> 
#include <fcntl.h> 
#include <sys/stat.h> 
#include <sys/types.h> 
#include <unistd.h> 
#include <iostream>
#include <algorithm>
#include <string>
#include <sstream>      // std::istringstream
#include <iomanip>      //setw, setfill

bool parse_srt_timestamp (std::string str, uint64_t *start_time_ms, int *durms)
{
    if ((str.size () == 39) &&
        (str[7] == ':') && (str[20] == '>') &&
        (str[32] == ':'))
    {
        int hh,mm,ss,ms;
        int ehh,emm,ess,ems;//e->end_time_ms
        uint64_t end_time_ms;

        sscanf (str.c_str (), "%07d:%02d:%02d,%03d --> %07d:%02d:%02d,%03d", &hh,&mm,&ss,&ms, &ehh,&emm,&ess,&ems);
        //sscanf (str.c_str (), "%02d:%02d:%02d,%03d", hh,mm,ss,ms);
        
        *start_time_ms = (uint64_t)(((((uint64_t)hh*60) + mm ) * 60 + ss ) * 1000 + ms);

        end_time_ms = (uint64_t)((((uint64_t)ehh*60) + emm ) * 60 + ess ) * 1000 + ems;

        *durms = (int)(end_time_ms - (*start_time_ms));

        return true;
    }
    return false;
}

int main (int argc, char **argv)
{

    static int fd;
    char * myfifo = argv[1]; 
    char str[1024];

    mkfifo(myfifo, 0666);

    std::string sub;

    while (1)
    {
        fd = open(myfifo, O_RDONLY);
        read (fd, str, 1024);
        sub.assign (str);
        std::istringstream is_line(str);
        std::string line;
        int i=0;
        while (std::getline (is_line, line))
        {
            i++;
            if (i == 1)
            {
                continue;
            }

            if (i == 2) 
            {
                uint64_t start_time_ms = 0;
                int durms = 0;
                if (parse_srt_timestamp (line, &start_time_ms, &durms))
                    std::cout << std::endl << "T:" << start_time_ms << " D:" << durms << std::endl;
            }
            else if  (line.size() > 0)
            {
                std::cout << line.size() << " " << line << std::endl;
            }

            if (line.empty ()) i = 0;
            
            std::cout << std::endl;
        }
        //printf ("read %s\n", str);
        close (fd);
    }
    return 0;
}
