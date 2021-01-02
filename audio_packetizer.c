#define _GNU_SOURCE
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
#include <getopt.h> 
#include <assert.h> 
#include <libgen.h> 

//---------------------------------------------------------------------------

#define SAMPLING_RATE       16000
#define BYTES_PER_SAMPLE    2
#define BYTES_PER_MS        ((SAMPLING_RATE * BYTES_PER_SAMPLE)/1000)

#define HEADER_LEN          14

#define DEF_CHUNK_DURATION_MS   32
#define DEF_SLEEP_BW_CHUNKS_MS  0
#define DEF_INPUT_FILEPATH      ""
#define DEF_OUTPUT_FILEPATH     ""
#define DEF_START_TIMESTAMP     0
#define DEF_EOF_WITH_0_SIZE     0

#define STDERR_FD           2

//---------------------------------------------------------------------------

const char *usage_format_str = "\n"
"NAME\n"
"    %s - packetizes pcm data for consumption by streaming_stt.py\n"
"\n"
"\n"
"SYNOPSIS\n"
"\n"
"    %s [-i audio.pcm] [-o packetized_audio]\n"
"       [-d duration_of_chunk_in_ms]  [-p start_ts]\n"
"       [-s sleep_bw_chunks_in_us] [-z] [-h]\n"
"\n"
"\n"
"DESCRIPTION\n"
"\n"
"    This program reads a pcm file via stdin (created through\n"
"    extract_pcm_for_sstt.sh) and creates packets on stdout.\n"
"    \n"
"    Each packet is composed of a 14 byte header and chunks of data from\n"
"    the pcm file.\n"
"\n"
"    The composition of a packet is as follows:\n"
"\n"
"    header\n"
"        signature       4 bytes     (fixed to 0xc0, 0xff, 0xee, 0xee)\n"
"        ts              8 bytes     (variable time stamp)\n"
"        size            2 bytes     (fixed to 32 * 16 * 2)\n"
"    data\n"
"        'size' amount of bytes read from the input pcm file\n"
"\n"
"    The chunk 'size' is derived as follows:\n"
"\n"
"    16Khz => 16000 samples/sec\n"
"    2 bytes per sample => (16000 * 2) samples/sec\n"
"    Samples per millisec = ((16000 * 2)/1000)\n"
"    Samples for 32 millisec = (32*(16000*2)/1000) = 32 * 16 * 2 bytes\n"
"\n"
"OPTIONS\n"
"\n"
"    -i  audio.pcm\n"
"        Pathname of the input pcm file. \n"
"        This is optional. Default is stdin.\n"
"\n"
"    -o  packetized_audio\n"
"        Pathname of the output file. \n"
"        This is optional. Default is stdout.\n"
"\n"
"    -d  duration_of_chunk_in_ms\n"
"        The duration of each chunk in milliseconds.\n"
"        This is optional. Default is 32 milliseconds.\n"
"\n"
"    -t  start_ts\n"
"        The starting timestamp value.\n"
"        This is optional. Default is 0.\n"
"\n"
"    -s  sleep_bw_chunks_in_us\n"
"        sleep duration between chunks in microseconds.\n"
"        This is optional. Default is 0.\n"
"\n"
"    -z  \n"
"        End of input signalled via a size of 0 in the packet header.\n"
"        This is optional.\n"
"\n"
"    -h\n"
"        This help.\n"
"        This is optional.\n"
"\n"
"\n"
"EXAMPLES\n"
"\n"
"    extract_pcm_for_sstt.sh foo.mp4 | %s -p 100 -z\n"
"\n";

//---------------------------------------------------------------------------

typedef struct
{
    // options
    
    unsigned       opt_chunk_duration_ms;
    unsigned       opt_sleep_between_chunks_ms;
    char          *opt_input_filepath;
    char          *opt_output_filepath;
    unsigned long  opt_start_timestamp;
    unsigned       opt_signal_eof_with_zero_size;
    unsigned       opt_verbose;

    // state

    unsigned       input_is_fifo;
    unsigned       output_is_fifo;
    unsigned       bytes_per_chunk;
    FILE          *in_fp;
    int            out_fd;
    unsigned long  timestamp;
    unsigned       buf_size;
    uint8_t       *buf;
    unsigned       num_packets_dumped;

    // misc

    const char    *progname;
}
t_aup_context;

//---------------------------------------------------------------------------

int 
file_exists
    (const char *file_path,
     unsigned   *is_named_pipe)
{
    struct stat stat_buf;
    int ret = 0;

    *is_named_pipe = 0;

    if (stat(file_path, &stat_buf) != 0)
    {
        goto end;
    }

    if (S_ISREG(stat_buf.st_mode))
    {
        ret = 1;
        goto end;
    }

    if (S_ISFIFO(stat_buf.st_mode))
    {
        ret = 1;
        *is_named_pipe = 1;
        goto end;
    }

end:
    return ret;
}


//---------------------------------------------------------------------------

void
usage
    (const char *progname)
{
    fprintf (
        stderr,
        usage_format_str,
        progname,
        progname,
        progname);
}

//---------------------------------------------------------------------------

void
set_state
    (t_aup_context *ctx,
     FILE          *in_fp,
     int            out_fd)
{
    ctx->in_fp  = in_fp;
    ctx->out_fd = out_fd;
    ctx->bytes_per_chunk = ctx->opt_chunk_duration_ms * BYTES_PER_MS;
    ctx->timestamp = ctx->opt_start_timestamp;
    ctx->buf_size = HEADER_LEN + ctx->bytes_per_chunk;
}

//---------------------------------------------------------------------------

int
init_state
    (t_aup_context *ctx)
{
    int   ret = 0;
    FILE *in_fp  = ctx->in_fp;
    int   out_fd = ctx->out_fd;

    // --- input ---

    if (*ctx->opt_input_filepath != '\0')
    {
        in_fp = fopen(ctx->opt_input_filepath, "rb");
        if (in_fp == NULL)
        {
            fprintf(stderr, 
                    "%s:error:%s while opening %s\n",
                    ctx->progname,
                    strerror(errno),
                    ctx->opt_input_filepath);
            goto end;
        }

        if (ctx->opt_verbose)
        {
            fprintf (stderr, 
                     "%s:info:opened input \"%s\"\n", 
                     ctx->progname,
                     ctx->opt_input_filepath);
        }
    }

    // --- output ---

    if (*ctx->opt_output_filepath != '\0')
    {
        out_fd = open(ctx->opt_output_filepath, 
                           O_CREAT | O_WRONLY,
                           S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);

        if (out_fd < 0)
        {
            fprintf(stderr, 
                    "%s:error:%s while opening %s\n",
                    ctx->progname,
                    strerror(errno),
                    ctx->opt_output_filepath);
            goto end;
        }
        if (ctx->opt_verbose)
        {
            fprintf (stderr, 
                     "%s:info:opened output \"%s\"\n", 
                     ctx->progname,
                     ctx->opt_output_filepath);
        }
    }

    set_state(ctx, in_fp, out_fd);

    // --- allocate buffer space ---

    ctx->buf = (uint8_t *) malloc (ctx->buf_size);
    if (! ctx->buf)
    {
        fprintf(stderr, 
                "%s:error:failure to allocated %u bytes of memory\n",
                ctx->progname,
                (unsigned) ctx->buf_size);
        goto end;
    }
    if (ctx->opt_verbose)
    {
        fprintf (stderr, 
                "%s:info:allocated %u bytes of memory\n",
                ctx->progname, (unsigned) ctx->buf_size);
    }


    ret = 1;

end:
    return ret;
}

//---------------------------------------------------------------------------

void
uninit_state
    (t_aup_context *ctx)
{
    if (ctx->in_fp == stdin || ctx->in_fp == NULL)
    {
        ;
    }
    else
    {
        fclose(ctx->in_fp);
        if (ctx->opt_verbose)
        {
            fprintf (stderr, 
                     "%s:info:closed input \"%s\"\n", 
                     ctx->progname, ctx->opt_input_filepath);
        }
    }

    if (ctx->out_fd == fileno(stdout) || ctx->out_fd == -1)
    {
        ;
    }
    else
    {
        close(ctx->out_fd);
        if (ctx->opt_verbose)
        {
            fprintf (stderr, 
                     "%s:info:closed output \"%s\"\n", 
                     ctx->progname, ctx->opt_output_filepath);
        }
    }

    if (ctx->buf)
        free(ctx->buf);

    memset(ctx, 0, sizeof(*ctx));
}

//---------------------------------------------------------------------------

void
init_context
    (t_aup_context *ctx,
     const char    *progname)
{
    memset(ctx, 0, sizeof(*ctx));

    ctx->opt_chunk_duration_ms = DEF_CHUNK_DURATION_MS;
    ctx->opt_sleep_between_chunks_ms = DEF_SLEEP_BW_CHUNKS_MS;
    ctx->opt_input_filepath = DEF_INPUT_FILEPATH;
    ctx->opt_output_filepath = DEF_OUTPUT_FILEPATH;
    ctx->opt_start_timestamp = DEF_START_TIMESTAMP;
    ctx->opt_signal_eof_with_zero_size = DEF_EOF_WITH_0_SIZE;

    set_state (ctx, stdin, fileno(stdout));

    ctx->progname = progname;
}

//---------------------------------------------------------------------------

void
uninit_context
    (t_aup_context *ctx)
{
    uninit_state (ctx);
}

//---------------------------------------------------------------------------

void
dump_context
    (const char *str,
     const t_aup_context *ctx)
{
    fprintf(stderr,
            "info:%s:%s:ctx{\n"
            "   <<options>>\n"
            "   opt_chunk_duration_ms = %u\n"
            "   opt_sleep_between_chunks_ms = %u\n"
            "   opt_input_filepath = %s\n"
            "   opt_output_filepath = %s\n"
            "   opt_start_timestamp = %lu\n"
            "   opt_signal_eof_with_zero_size = %u\n"
            "   opt_verbose = %u\n"
            "   input_is_fifo = %u\n"
            "   output_is_fifo = %u\n"
            "   bytes_per_chunk = %u\n"
            "   <<state>>\n"
            "   in_fp = %p\n"
            "   out_fd = %d\n"
            "   timestamp = %lu\n"
            "   buf_size = %u\n"
            "   buf = %p\n"
            "   num_packets_dumped = %u\n"
            "}\n",

             ctx->progname, str,
             ctx->opt_chunk_duration_ms,
             ctx->opt_sleep_between_chunks_ms,
             ctx->opt_input_filepath,
             ctx->opt_output_filepath,
             ctx->opt_start_timestamp,
             ctx->opt_signal_eof_with_zero_size,
             ctx->opt_verbose,
             ctx->input_is_fifo, 
             ctx->output_is_fifo,
             ctx->bytes_per_chunk,
             ctx->in_fp,
             ctx->out_fd,
             ctx->timestamp,
             ctx->buf_size,
             ctx->buf,
             ctx->num_packets_dumped);
}

//---------------------------------------------------------------------------

int 
set_cmdline_options
    (t_aup_context *ctx,
     int            argc, 
     char         **argv)
{
    int c, n, error = 0;

    // get options and values

    while ((c = getopt (argc, argv, "i:o:d:t:s:zvh")) != -1)
    {
        switch(c)
        {
            case 'i':
                if (! file_exists (optarg, &ctx->input_is_fifo))
                {
                    fprintf(stderr, 
                            "%s:error:%s:does not exist\n", 
                            ctx->progname, optarg);
                    error = 1;
                }
                ctx->opt_input_filepath = strdup(optarg);
                break;

            case 'o':
                file_exists (optarg, &ctx->output_is_fifo);
                ctx->opt_output_filepath = strdup(optarg);
                break;

            case 'd':
                n = sscanf(optarg, "%u", &ctx->opt_chunk_duration_ms);
                if (n != 1)
                {
                    fprintf(stderr, 
                            "%s:error:unable to parse value for -d option\n",
                            ctx->progname);
                    error = 1;
                }
                break;

            case 't':
                //https://stackoverflow.com/questions/6993132/format-specifiers-for-uint8-t-uint16-t
                n = sscanf(optarg, "%lu", &ctx->opt_start_timestamp);
                if (n != 1)
                    fprintf(stderr, 
                            "%s:error:unable to parse value for -t option\n",
                            ctx->progname);
                break;

            case 's':
                n = sscanf(optarg, "%u", &ctx->opt_sleep_between_chunks_ms);
                if (n != 1)
                {
                    fprintf(stderr, 
                            "%s:error:unable to parse value for -s option\n",
                            ctx->progname);
                    error = 1;
                }
                break;

            case 'z':
                ctx->opt_signal_eof_with_zero_size = 1;
                break;

            case 'v':
                ctx->opt_verbose = 1;
                break;

            case 'h':
                usage(ctx->progname);
                exit(0);

            default:
                fprintf(stderr, "unknown option -%c\n", c);
                goto end;
        }
    }

    if (error)
        goto end;

    // validate options and values

    if (ctx->opt_chunk_duration_ms == 0)
    {
        fprintf(stderr, 
                "%s:error:invalid value %u for -d option\n",
                ctx->progname,
                ctx->opt_chunk_duration_ms);
        error = 1;
        goto end;
    }

end:
    return (error == 0);
}


//---------------------------------------------------------------------------

void
set_header_signature
    (t_aup_context *ctx)
{
    uint8_t *buf = ctx->buf;

    buf[0] = 0xc0;
    buf[1] = 0xff;
    buf[2] = 0xee;
    buf[3] = 0xee;
}

//---------------------------------------------------------------------------

void
set_header_timestamp
    (t_aup_context *ctx)
{
    uint8_t *buf = ctx->buf;
    unsigned long ts = ctx->timestamp;

    buf[4]  = ts;
    buf[5]  = ts >> 8;
    buf[6]  = ts >> 16;
    buf[7]  = ts >> 24;
    buf[8]  = ts >> 32;
    buf[9]  = ts >> 40;
    buf[10] = ts >> 48;
    buf[11] = ts >> 56;
}

//---------------------------------------------------------------------------

void
set_header_chunk_size
    (t_aup_context *ctx,
     unsigned size)
{
    uint8_t *buf = ctx->buf;

    buf[12] = size;
    buf[13] = size >> 8;
}

//---------------------------------------------------------------------------

int
dump_buf
    (t_aup_context *ctx,
     size_t size)
{
    int fret = 0;

    int ret = write(ctx->out_fd, ctx->buf, size);
    if (ret != size)
        goto end;

    ctx->timestamp += ctx->opt_chunk_duration_ms;
    ++ctx->num_packets_dumped;

    fret = 1;

end:
    return fret;
}

//---------------------------------------------------------------------------

int
run
    (t_aup_context *ctx)
{
    int ret = 1;

    set_header_signature  (ctx);    // __1__
    set_header_timestamp  (ctx);    // __2__
    set_header_chunk_size (ctx, ctx->bytes_per_chunk);    // __3__


    if (ctx->opt_verbose)
        write(STDERR_FD, "\n", 1);

    while (fread (ctx->buf + HEADER_LEN, 1, ctx->bytes_per_chunk, ctx->in_fp) 
           == ctx->bytes_per_chunk)
    {
        // set_header_signature is as set in (__1__) above
        set_header_timestamp (ctx);
        // set_header_chunk_size is as set in (__3__) above

        if (! dump_buf(ctx, ctx->buf_size))
        {
            fprintf(stderr, "%s:error:on write\n", ctx->progname);
            ret = 0;
            goto end;
        }

        if (ctx->opt_sleep_between_chunks_ms)
            usleep (ctx->opt_sleep_between_chunks_ms);
    }


    if (ctx->opt_signal_eof_with_zero_size)
    {
        // set_header_signature is as set in (__1__) above
        set_header_timestamp  (ctx);
        set_header_chunk_size (ctx, 0);

        if (! dump_buf(ctx, HEADER_LEN))
        {
            fprintf(stderr, "%s:error:on write\n", ctx->progname);
            ret = 0;
            goto end;
        }
    }

    
end:

    return ret;
}

//---------------------------------------------------------------------------

int main (int argc, char **argv)
{
    int ret, main_ret = 0;
    t_aup_context ctx;
    char *progname = basename(strdupa(argv[0]));

    assert(sizeof(unsigned) == 4);
    assert(sizeof(unsigned long) == 8);

    init_context (&ctx, progname);

    ret = set_cmdline_options (&ctx, argc, argv);
    if (! ret)
    {
        main_ret = 1;
        goto end;
    }

    ret = init_state (&ctx);
    if (! ret)
    {
        main_ret = 1;
        goto end;
    }

    if (ctx.opt_verbose)
        dump_context ("before run", &ctx);

    ret = run (&ctx);
    if (! ret)
    {
        main_ret = 1;
        goto end;
    }

end:
    if (ctx.opt_verbose)
        dump_context ("before end", &ctx);

    uninit_context (&ctx);

    return main_ret;
}

