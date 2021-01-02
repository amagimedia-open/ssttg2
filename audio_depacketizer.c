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
#include <time.h> 

//---------------------------------------------------------------------------

#define HEADER_LEN          14
#define SIGNATURE           0xc0ffeeee
#define READ_BLOCK_SIZE     512

#define DEF_EOF_ON_0_SIZE   0
#define DEF_INPUT_FILEPATH  ""
#define DEF_OUTPUT_FILEPATH ""
#define DEF_FORWARD_MODE    0

//---------------------------------------------------------------------------

const char *usage_format_str = "\n"
"NAME\n"
"    %s - depacketizes pcm data\n"
"\n"
"\n"
"SYNOPSIS\n"
"\n"
"    %s [-i packetized_audio] [-o audio.pcm]\n"
"       [-z] [-h]\n"
"\n"
"\n"
"DESCRIPTION\n"
"\n"
"    This program reads a packetized pcm stream via stdin \n"
"    (created through sstt_audio_packetizer) and dumps pcm data on stdout.\n"
"    \n"
"\n"
"OPTIONS\n"
"\n"
"    -i  packetized_audio\n"
"        Pathname of the input file. \n"
"        This is optional. Default is stdin.\n"
"\n"
"    -o  audio.pcm\n"
"        Pathname of the output pcm file. \n"
"        This is optional. Default is stdout.\n"
"\n"
"    -f\n"
"        Forward mode. The incoming packet echoed to output.\n"
"        It is recommended that the -z option is specified along with this\n"
"        option to terminate the program upon reception of 0 size in packet\n"
"        header\n"
"        This is optional. Default is to strip the packet header and outut\n"
"        only pcm data.\n"
"\n"
"    -z  \n"
"        End of input signalled via a size of 0 in the packet header.\n"
"        This is optional.\n"
"\n"
"    -v  \n"
"        Dumps debug information on stderr.\n"
"        This is optional.\n"
"\n"
"    -h\n"
"        This help.\n"
"        This is optional.\n"
"\n"
"\n"
"EXAMPLES\n"
"\n"
"    extract_pcm_for_sstt.sh foo.mp4  |\\\n"
"    sstt_audio_packetizer.sh -z |\\\n"
"    %s -z > foo.pcm\n"
"\n";

//---------------------------------------------------------------------------

typedef struct
{
    // options
    
    char          *opt_input_filepath;
    char          *opt_output_filepath;
    unsigned       opt_eof_on_zero_size;
    unsigned       opt_forward_mode;
    unsigned       opt_verbose;
    unsigned       opt_verbose_count;

    // state

    unsigned       input_is_fifo;
    unsigned       output_is_fifo;
    FILE          *in_fp;
    int            out_fd;
    unsigned       num_packets_read;
    unsigned       in_offset;
    
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
                     ctx->progname,
                     ctx->opt_input_filepath);
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
                     ctx->progname,
                     ctx->opt_output_filepath);
        }
    }

    memset(ctx, 0, sizeof(*ctx));
}

//---------------------------------------------------------------------------

void
init_context
    (t_aup_context *ctx,
     const char    *progname)
{
    memset(ctx, 0, sizeof(*ctx));

    ctx->opt_input_filepath = DEF_INPUT_FILEPATH;
    ctx->opt_output_filepath = DEF_OUTPUT_FILEPATH;
    ctx->opt_eof_on_zero_size = DEF_EOF_ON_0_SIZE;
    ctx->opt_forward_mode = DEF_FORWARD_MODE;

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
            "   opt_input_filepath = %s\n"
            "   opt_output_filepath = %s\n"
            "   opt_eof_on_zero_size = %u\n"
            "   opt_forward_mode = %u\n"
            "   opt_verbose = %u\n"
            "   input_is_fifo = %u\n"
            "   output_is_fifo = %u\n"
            "   <<state>>\n"
            "   out_fd = %d\n"
            "   num_packets_read = %u\n"
            "   in_offset = %u\n"
            "}\n",
            /* in_fp = %p\n" */

             ctx->progname, str,
             ctx->opt_input_filepath,
             ctx->opt_output_filepath,
             ctx->opt_eof_on_zero_size,
             ctx->opt_forward_mode,
             ctx->opt_verbose,
             ctx->input_is_fifo, 
             ctx->output_is_fifo,
            /* ctx->in_fp, */
             ctx->out_fd,
             ctx->num_packets_read,
             ctx->in_offset);
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

    while ((c = getopt (argc, argv, "i:o:d:t:s:zfvh")) != -1)
    {
        switch(c)
        {
            case 'i':
                if (! file_exists (optarg, &ctx->input_is_fifo))
                {
                    fprintf(stderr, 
                            "%s:error:%s:does not exist\n", 
                            ctx->progname,
                            optarg);
                    error = 1;
                }
                ctx->opt_input_filepath = strdup(optarg);
                break;

            case 'o':
                file_exists (optarg, &ctx->output_is_fifo);
                ctx->opt_output_filepath = strdup(optarg);
                break;

            case 'z':
                ctx->opt_eof_on_zero_size = 1;
                break;

            case 'f':
                ctx->opt_forward_mode = 1;
                break;

            case 'v':
                ctx->opt_verbose = 1;
                ++ctx->opt_verbose_count;
                break;

            case 'h':
                usage(ctx->progname);
                exit(0);

            default:
                fprintf(stderr, "unknown option -%c\n", c);
                goto end;
        }
    }

end:
    return (error == 0);
}


//---------------------------------------------------------------------------

unsigned
get_header_signature
    (uint8_t *buf)
{
    unsigned out;

    out  =  buf[3];
    out |= (buf[2]  << 8);
    out |= (buf[1]  << 16);
    out |= (buf[0]  << 24);

    return out;
}

//---------------------------------------------------------------------------

unsigned long
get_header_timestamp
    (uint8_t *buf)
{
    unsigned long out;

    out  =   (unsigned long)buf[4];
    out |= (((unsigned long)buf[5]  ) << 8);
    out |= (((unsigned long)buf[6]  ) << 16);
    out |= (((unsigned long)buf[7]  ) << 24);
    out |= (((unsigned long)buf[8]  ) << 32);
    out |= (((unsigned long)buf[9]  ) << 40);
    out |= (((unsigned long)buf[10] ) << 48);
    out |= (((unsigned long)buf[11] ) << 56);

    return out;
}

//---------------------------------------------------------------------------

unsigned
get_header_chunk_size
    (uint8_t *buf)
{
    unsigned out;

    out  =  buf[12];
    out |= (buf[13] << 8);

    return out;
}

//---------------------------------------------------------------------------

/*
 * note that fseek is not used as the input may be stdin
 */
int
read_and_dump_n_bytes
    (t_aup_context *ctx,
     uint8_t        hdr_buf[HEADER_LEN],
     unsigned       n)
{
    int ret = 1;
    uint8_t  data_buf[READ_BLOCK_SIZE];

    if (ctx->opt_forward_mode)
    {
        int n_written = write(ctx->out_fd, hdr_buf, HEADER_LEN);
        if (n_written != HEADER_LEN)
        {
            ret = 0;
            goto end;
        }
    }

    while (n > 0)
    {
        unsigned to_read = n;

        if (to_read > READ_BLOCK_SIZE)
            to_read = READ_BLOCK_SIZE;

        size_t n_read = fread (data_buf, 1, to_read, ctx->in_fp);
        if (n_read < to_read)
            break;

        int n_written = write(ctx->out_fd, data_buf, n_read);
        if (n_written != n_read)
        {
            ret = 0;
            goto end;
        }

        n -= n_read;
    }

end:
    return ret;
}

//---------------------------------------------------------------------------

int
run
    (t_aup_context *ctx)
{
    int     ret = 1;
    uint8_t hdr_buf[HEADER_LEN];

    while (fread (hdr_buf, 1, HEADER_LEN, ctx->in_fp) == HEADER_LEN)
    {
        ++ctx->num_packets_read;

        unsigned sig = get_header_signature (hdr_buf);
        if (sig != SIGNATURE)
        {
            fprintf (stderr, 
                     "%s:error:bad signature at offset %u. expected %x got %x.\n", 
                     ctx->progname, ctx->in_offset, (unsigned) SIGNATURE, sig);
            ret = 0;
            goto end;
        }

        unsigned long ts = get_header_timestamp (hdr_buf);
        unsigned size = get_header_chunk_size (hdr_buf);
        
        if (ctx->opt_verbose_count > 1)
        {
            time_t t;
            time(&t);

            fprintf (stderr, 
                     "%s:info:time=%u, pkt#=%08u, sig=%08x, ts=%016lu, sz=%08u\n", 
                     ctx->progname, (unsigned) t, ctx->num_packets_read, sig, ts, size);
            fflush (stderr);
        }

        if (! read_and_dump_n_bytes (ctx, hdr_buf, size))
        {
            fprintf (stderr, 
                     "%s:error:during read/write\n",
                     ctx->progname);
            ret = 0;
            goto end;
        }

        if (size == 0 && ctx->opt_eof_on_zero_size)
        {
            if (ctx->opt_verbose)
            {
                fprintf (stderr, 
                         "%s:info:breaking out on 0 size\n", 
                         ctx->progname);
            }
            break;
        }

        ctx->in_offset += (HEADER_LEN + size);
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

