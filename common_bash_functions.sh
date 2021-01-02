#----------------------------------------------------------------------------
# RELATING TO LOG MESSAGES

function error_message
{
    local _message="$1"

    echo "`basename $0`:error:$_message" >&2
}

function debug_message
{
    local _message="$1"

    echo "`basename $0`:debug:$_message" >&2
}

function warn_message
{
    local _message="$1"

    echo "`basename $0`:warn:$_message" >&2
}

function info_message
{
    local _message="$1"

    echo "`basename $0`:info:$_message" >&2
}

function name_not_found_error
{
    local _name="$1"
    local _section_name="$2"
    local _filepath="$3"

    error_message "name ($_name) or section ($_section_name) not found in $_filepath"
}

#----------------------------------------------------------------------------
# RELATING TO PROCESSESS

function term_bg_process
{
    local _bgid=$1

    if ((_bgid > 0))
    then
        if ps -p $_bgid > /dev/null
        then
            kill -9 $_bgid
        fi
    fi
}

function get_pids_of
{
    local _process_name="$1"

    pidof "$_process_name" | sed 's/ /\n/g' | sort
}

function get_added_pids_of
{
    # usage
    # get_pids_of "foo" > $tmp1
    # start another instance of "foo"
    # added_pid=`get_added_pid_of "foo" $tmp1`

    local _process_name="$1"
    local _prior_pids_file="$2"

    comm -13 $_prior_pids_file <(get_pids_of $_process_name)
}

function is_pid_alive
{
    local _pid=$1

    kill -s 0 $_pid 1>/dev/null 2>&1
}

function kill_pid
{
    local _pid=$1

    if ! is_pid_alive $_pid
    then
        return 0
    fi

    kill $_pid 1>/dev/null 2>&1

    if is_pid_alive $_pid
    then
        kill -9 $_pid 1>/dev/null 2>&1
    fi

    is_pid_alive $_pid
}

#----------------------------------------------------------------------------
# RELATING TO NUMBERS

function is_a_number
{
    local _value="$1"
    if [[ $_value =~ ^[0-9][0-9]*$ ]]
    then
        return 0
    else
        return 1
    fi
}

function is_a_integer
{
    local _value="$1"
    if [[ $_value =~ ^-[0-9][0-9]*$ ]]
    then
        return 0
    else
        return 1
    fi
}

function check_if_value_is_within_bounds
{
    local _val="$1"
    local _begin="$2"
    local _end="$3"
    local _tolerance="$4"
    local _ret=0            # success

    if (($_val < $_begin))
    then
        (($_begin - $_val > $_tolerance)) && { _ret=1; }
    elif (($_val > $_end))
    then
        (($_val - $_end > $_tolerance)) && { _ret=1; }
    else
        : # $_begin <= $_val <= $_end
    fi

    return $_ret
}

function min
{
    local _a=$1
    local _b=$2

    echo $((_a <= _b ? _a : _b))
}

function max
{
    local _a=$1
    local _b=$2

    echo $((_a >= _b ? _a : _b))
}

#----------------------------------------------------------------------------
# RELATING TO wxh functions

function is_a_size_spec
{
    local _size_spec="$1"

    #must be of the form WxH or WXH

    if [[ $_size_spec =~ ^[0-9][0-9]*[xX][0-9][0-9]*$ ]]
    then
        return 0
    else
        return 1
    fi
}

#----------------------------------------------------------------------------
# RELATING TO DATE AND TIME

function get_day_of
{
    # 'get_day_of n' where n in an integer
    # examples
    # get_day_of 0  == today
    # get_day_of -1 == yesterday
    # get_day_of 1  == tomorrow
    # get_day_of -2 == the day before yesterday

    local _rel_day="$1"

    date -d "$_rel_day day" +%F
}

function change_to_iso_time
{
    local _in_time="$1"
    local _iso_time="${_in_time/ /T}"
    
    echo "$_iso_time"
}

function change_iso_to_epoch_time
{
    _iso_time="$1"
    local _epoch_time="`date --date="$_iso_time" +%s`"

    echo "$_epoch_time"
}

function current_datetime_str
{
    echo "`date +%Y_%m_%d_%H_%M_%S_%N`"
}

function curr_date_time_str
{
    date +%Y_%m_%d_%H_%M_%S_%N
}

#----------------------------------------------------------------------------
# RELATING TO FILES

function get_file_size
{
    local _filepath="$1"
    local _size=0
    local _ret=1

    if _size=`stat -c %s $_filepath`
    then
        _ret=0
    fi

    echo "$_size"
    return $_ret
}

function is_file_empty
{
    local _filepath="$1"
    local _size=0

    if _size=`get_file_size $_filepath`
    then
        if ((_size==0))
        then
            return 0
        fi
    fi

    return 1
}

function create_file
{
    local _filepath="$1"

    if [[ $_filepath = "/dev/null" ]]
    then
        return 0
    fi

    if [[ -f "$_filepath" ]]
    then
        cat /dev/null > $_filepath
        return 0
    fi

    local _dirpath="`dirname $_filepath`"

    if [[ ! -d "$_dirpath" ]]
    then
        if ! mkdir -p "$_dirpath"
        then
            echo "$FUNCNAME: folder $_dirpath could not be created" >&2
            return 1
        fi
    fi

    if ! touch "$_filepath"
    then
        echo "$FUNCNAME: file $_filepath could not be created" >&2
        return 1
    fi

    return 0
}

function create_reserved_file
{
    #TODO: better way ?

    local _filepath="$1"
    local _sudo_password="$2"

    local _dirpath="`dirname $_filepath`"

    if [[ ! -d "$_dirpath" ]]
    then
        if ! echo "$_sudo_password" | sudo -S mkdir -p "$_dirpath"
        then
            echo "$FUNCNAME: folder $_dirpath could not be created" >&2
            return 1
        fi
    fi

    if ! echo "$_sudo_password" | sudo -S  touch "$_filepath"
    then
        echo "$FUNCNAME: file $_filepath could not be created" >&2
        return 1
    fi

    return 0
}

function get_bare_filename
{
    local _path="$1"
    local _basename="`basename $_path`"
    echo ${_basename%.*}
}

function rm_other_than
{
    local _tmp="$1"
    shift 
    local _folder="$1"
    shift 

    > $_tmp
    for i in "$@"
    do
        echo "$i" >> $_tmp
    done

    if pushd $_folder > /dev/null
    then
        rm -vf `ls $_folder | cat | grep -v -F -f $_tmp`
        popd > /dev/null
    fi
}

#----------------------------------------------------------------------------
# RELATING TO FOLDERS

function clear_folder
{
    local _folder="$1"

    (
        local _i

        if cd $_folder 2>/dev/null
        then
            for _i in * .*
            do
                [[ $_i == '.' ]]  && { continue; }
                [[ $_i == '..' ]] && { continue; }
                rm -rf $_i
            done
            exit 0
        fi
        exit 1
    )
    return $?
}

function safe_clear_folder
{
    local _folder="$1"

    if [[ -n "$_folder" ]]
    then
        if [[ -d "$_folder" ]]
        then
            local _rp="`realpath $_folder`"
            if [[ "$_rp" =~ $HOME ]]
            then
                if clear_folder $_rp
                then
                    return 0
                fi
            fi
        fi
    fi

    return 1
}

function safe_rm_folder
{
    local _folder="$1"

    if ! safe_clear_folder $_folder
    then
        return 1
    fi

    rmdir $_folder
}

function create_fresh_folder
{
    local _folder="$1"

    safe_rm_folder $_folder
    mkdir -p $_folder
}

function create_folder
{
    local _folder="$1"

    if [[ ! -d "$_folder" ]]
    then
        mkdir -p "$_folder"
    fi
}

function are_folders_mounted
{
    local _asset_mapping_filepath="$1"
    local _tmp="$2"
    local _debug="$3"

    local _path=""
    local _mounted=0

    echo "cat <<EOD" > $_tmp
    cat $_asset_mapping_filepath >> $_tmp
    echo "EOD" >> $_tmp

    source $_tmp | sponge $_tmp
    ((_debug)) && { csvlook $_tmp; }

    #csvcut -c LOCAL $_tmp | sed '1d' | sponge $_tmp
    #((_debug)) && { csvlook -H $_tmp; }

    for _path in `cat $_tmp`
    do
        if [[ -d "$_path" ]]
        then
            if ! ls -l $_path | grep -q -e 'total 0'
            then
                echo "$FUNCNAME: folder $_path mounted !" >&2
                _mounted=1
            fi
        fi
    done

    if ((_mounted))
    then
        return 0
    else
        return 1
    fi
}

#----------------------------------------------------------------------------
# RELATING TO CSV FILES

function get_column_names
{
    local _csv_filepath="$1"

    csvcut -n $_csv_filepath | gawk '{print $2;}' | sort
}

function is_column_present
{
    local _csv_filepath="$1"
    local _column_name="$2"

    if get_column_names $_csv_filepath | grep -q -w -e "$_column_name"
    then
        return 0
    else
        return 1
    fi
}

function are_needed_columns_present
{
    local _csv_filepath="$1"
    local _needed_column_names_filepath="$2"

    #comm: what an utility !. did not know of this earlier.
    #here we get the lines that are present in _needed_cols_filepath
    #and not in _csv_filepath

    local _num_cols_absent=`
        get_column_names $_csv_filepath |\
        comm -2 -3 $_needed_column_names_filepath - |\
        wc -l`

    ((_num_cols_absent)) && { return 1; }
    return 0
}

function are_needed_columns_present_2
{
    local _csv_filepath="$1"
    local _column_names="$2"
    local _tmp=$3

    echo "$_column_names" | tr ',' '\n' | sort > $_tmp

    if are_needed_columns_present $_csv_filepath $_tmp
    then
        return 0
    else
        return 1
    fi
}

function get_column_number
{
    local _csv_filepath="$1"
    local _column_name="$2"

    local _column_number=`csvcut -n $_csv_filepath |\
               grep -F -e "$_column_name" |\
               gawk -F '[ \t]*:[ \t]*' '{print $1;}' |\
               sed 's/[ \t]//g'`

    echo "$_column_number"
}

function csvfyLines
{
    local _n_lines="$1"

    gawk -v v_n_lines="$_n_lines" \
    '
     BEGIN \
     {
        count = 0
     }

     {
        current=$0
        ++count
        lines[count]=current

        if (count == v_n_lines)
        {
            concatLines()
            count = 0
        }
    }

    END \
    {
        concatLines()
    }

    function concatLines()
    {
        if (count > 0)
        {
            output = lines[1]
            for (i = 2; i <= count; ++i)
                output = output "," lines[i]
            print output
        }
    }
    '
}

#----------------------------------------------------------------------------
# RELATING TO NAME VALUE FILES

function get_named_value
{
    local _filepath="$1"
    local _name="$2"

    local _value="`gawk -F '[ \t]*=[ \t]*' \
                        -v v_name=\"$_name\" \
                        '($1 == v_name) { print $2; }' \
                        $_filepath`"
    echo "$_value"
}

function get_named_value_ex
{
    local _filepath="$1"
    local _name="$2"
    local _value="`get_named_value $_filepath $_name`"

    echo "$_value"
    [[ -z "$_value" ]] && { return 1; }
    return 0
}

function replace_named_value
{
    local _filepath="$1"
    local _name="$2"
    local _value="$3"

    gawk -F '[ \t]*=[ \t]*' \
            -v v_name="$_name" \
            -v v_value="$_value" \
            '($1 == v_name) { print v_name "=" v_value; replaced=1; next; }
            { print; }
            END { if (! replaced) print v_name "=" v_value; }' \
            $_filepath |\
    sponge $_filepath
}

function del_named_value
{
    local _filepath="$1"
    local _name="$2"

    gawk -F '[ \t]*=[ \t]*' \
            -v v_name="$_name" \
            '($1 != v_name) { print; }' \
            $_filepath |\
    sponge $_filepath
}

#----------------------------------------------------------------------------
# RELATING TO INI FILES

function get_config_name_value_sx
{
    local _name="$1"    # this can be a regex
    local _name_value_filepath="$2"

    # the name is of the form ini_file_name/section_name/name
    # the output of cats-gen-ini-section-name-values.sh has
    # be used here

    local _matched_line=`grep -m 1 -e "$_name" $_name_value_filepath`

    if [[ -z "$_matched_line" ]]
    then
        return 1
    fi

    local _value=${_matched_line#*=}

    echo "$_value"
    return 0
}

function get_config_name_value
{
    local _name="$1"
    local _section_name="$2"
    local _filepath="$3"

    local _value=""
    local _ret=0
    local _section_name_option_n_value=""

    if [[ -n "$_section_name" ]]
    then
        _section_name_option_n_value="-s $_section_name"
    fi

    _value=`mi2a-get-ini-value.sh -n "$_name" $_section_name_option_n_value $_filepath`
    _ret=$?
    if ((_ret != 0))
    then
        name_not_found_error "$_name" "$_section_name" $_filepath
        return 1
    fi

    local _name_value="$_filepath/$_section_name/$_name=$_value"

    if ((OPT_DEBUG))
    then
        echo "$_name_value" >&2
    fi

    echo $_name_value
    return 0
}

function get_section_name
{
    local _ini_filepath="$1"
    local _regex="$2"

    gawk \
    -v v_regex="$_regex" \
    '
    /^\[/ \
    {
        section_name = $0
        next
    }

    {
        if ($0 ~ v_regex)
        {
            gsub(/[\[\]]/,"",section_name)
            print section_name
            exit
        }
    }
    ' \
    $_ini_filepath
}

function filter_section_name_values
{
    local _ini_filepath="$1"
    local _section_name="$2"

    gawk \
    -v v_section_name="$_section_name" \
    '
    BEGIN \
    {
        if (v_section_name !~ /^\[/)
            v_section_name = "[" v_section_name "]"
    }

    /^[ \t]*$/ \
    {
        next
    }

    /^#/ \
    {
        next
    }

    /^\[/ \
    {
        if (section_started)
            exit
    }

    {
        if (section_started)
        {
            print
            next
        }
    }

    ($0 == v_section_name) \
    {
        section_started = 1
        next
    }
    ' \
    $_ini_filepath
}

#----------------------------------------------------------------------------
# RELATING TO SSH

function ssh_exec_command
{
    local _user_at_machine="$1"
    local _password="$2"
    local _command="$3"

    (
        export SSHPASS="$_password"
        #https://stackoverflow.com/questions/9393038/ssh-breaks-out-of-while-loop-in-bash
        sshpass -e ssh -q $MI2A_FP_BYPASS_ARGS -n -T $_user_at_machine "$_command"
    )
    local _ret=$?

    return $_ret
}

function ssh_exec_command_with_pseudo_tty
{
    local _user_at_machine="$1"
    local _password="$2"
    local _command="$3"

    (
        export SSHPASS="$_password"
        #https://stackoverflow.com/questions/9393038/ssh-breaks-out-of-while-loop-in-bash
        sshpass -e ssh -q $MI2A_FP_BYPASS_ARGS -n -tt $_user_at_machine "$_command"
    )
    local _ret=$?

    return $_ret
}

#function ssh_exec_commands_on_stdin
#{
#    #TODO: 
#    #dont use this function, problems exists
#
#    local _user_at_machine="$1"
#    local _password="$2"
#    local _require_tty="$3"
#
#    local _pseudo_terminal_option="-T"
#    ((_require_tty)) && { _pseudo_terminal_option="-tt"; }
#
#    (
#        export SSHPASS="$_password"
#        cat | sshpass -e ssh $_pseudo_terminal_option $_user_at_machine
#    )
#    local _ret=$?
#
#    return $_ret
#}

#----------------------------------------------------------------------------
# RELATING TO SCP

function copy_to_remote
{
    local _user_at_machine="$1"
    local _password="$2"
    local _local_filepath="$3"
    local _remote_path="$4"
    local _debug_mode="$5"

    (
        local _remote_folder="`dirname $_remote_path`"

        if ! ssh_exec_command "$_user_at_machine" "$_password" "mkdir -p $_remote_folder"
        then
            if ((_debug_mode))
            then
                echo "$FUNCNAME: failed to create remote folder $_remote_folder" >&2
            fi
            exit 1
        fi

        export SSHPASS="$_password"

        if ! sshpass -e scp -q $MI2A_FP_BYPASS_ARGS "$_local_filepath" "$_user_at_machine:$_remote_path"
        then
            if ((_debug_mode))
            then
                echo "$FUNCNAME: failed to scp $_local_filepath $_user_at_machine:$_remote_path" >&2
            fi
            exit 1
        fi
    )
    local _ret=$?

    return $_ret
}

function copy_from_remote
{
    local _user_at_machine="$1"
    local _password="$2"
    local _remote_path="$3"
    local _local_filepath="$4"
    local _debug_mode="$5"

    (
        RET=0
        export SSHPASS="$_password"

        if ! sshpass -e scp -q $MI2A_FP_BYPASS_ARGS "$_user_at_machine:$_remote_path" "$_local_filepath"
        then
            RET=1
        fi

        if ((_debug_mode))
        then
            STATUS="passed"
            ((RET)) && { STATUS="failed"; }
            echo "scp $_user_at_machine:$_remote_path $_local_filepath $STATUS" >&2
        fi

        exit $RET
    )
    local _ret=$?

    return $_ret
}

#----------------------------------------------------------------------------
# RELATING TO TEMP FILES
#
# these functions use two environment variables G_MAX_TMP_FILES and 
# G_TMP_FILES_LIST.  An example definition of these variables is
# G_MAX_TMP_FILES=5
# G_TMP_FILES_LIST=`mktemp`
# see test_tmp_file_fnxs function for usage of these functions

function create_tmp_files
{
    local _count=0
    local _tmp

    while ((_count < $G_MAX_TMP_FILES))
    do
        _tmp=`mktemp`
        echo "$_tmp 0" >> $G_TMP_FILES_LIST
        ((_count += 1))

        #mi2p_debug_message "tmp file $_tmp created" >&2
    done
}

function delete_tmp_files
{
    local _tmp

    gawk '{print $1; }' $G_TMP_FILES_LIST |\
    while read _tmp
    do
        #mi2p_debug_message "deleting tmp file $_tmp" >&2
        rm $_tmp
    done
}

function escape_slashes
{
    local _in="$1"

    echo "${_in//\//\\/}"
}

function get_tmp_file
{
    local _line_number=`grep -m 1 -n -e '0$' $G_TMP_FILES_LIST | cut -f 1 -d :`
    if [[ -z $_line_number ]]
    then
        mi2p_error_message "$FUNCNAME: no more tmp files to dispense"
        return 1
    fi

    local _tmp="`sed -n \"${_line_number}p\" $G_TMP_FILES_LIST | gawk '{print $1;}'`"
    local _escaped_tmp="`escape_slashes $_tmp`"

    sed -i "${_line_number} s/.*/$_escaped_tmp 1/" $G_TMP_FILES_LIST

    #mi2p_debug_message "$FUNCNAME: dispensing $_tmp"
    echo "$_tmp"
}

function release_tmp_file
{
    local _tmp
    local _escaped_tmp

    while [[ $# -gt 0 ]]
    do
        _tmp="$1"
        _escaped_tmp="`escape_slashes $_tmp`"

        #mi2p_debug_message "$FUNCNAME: releasing $_tmp"
        sed -i "/$_escaped_tmp/ s/.*/$_escaped_tmp 0/" $G_TMP_FILES_LIST

        shift
    done
}

function reset_tmp_files
{
    sed -i 's/1$/0/' $G_TMP_FILES_LIST
}

function list_tmp_files
{
    cat $G_TMP_FILES_LIST
}

function test_tmp_file_fnxs
{
    list_tmp_files

    local _tmp1=`get_tmp_file`
    local _tmp2=`get_tmp_file`

    list_tmp_files

    release_tmp_file $_tmp1

    list_tmp_files

    local _tmp3=`get_tmp_file`

    list_tmp_files

    release_tmp_file $_tmp2 $_tmp3

    list_tmp_files
}

#----------------------------------------------------------------------------
# RELATING TO URL

function file_url_of
{
    local _filepath="$1"

    if [[ ! -e $_filepath ]]
    then
        echo ""
        return 1
    fi

    local _abs_filepath="`readlink -e $_filepath`"

    echo "file://$_abs_filepath"
    return 0
}

#----------------------------------------------------------------------------
# RELATING TO HTML

function create_html_with_image
{
    local _title="$1"
    local _img_filepath="$2"

    local _img_file_url

    if ! _img_file_url="`file_url_of $_img_filepath`"
    then
        echo ""
        return 1
    fi

cat <<EOD
<html>
<head> 
    <title>$_title</title>
</head>
<body>
    <img SRC="$_img_file_url"/>
</body>
</html>
EOD

    return 0
}

#----------------------------------------------------------------------------
# RELATING TO IP

function get_nw_intf_list
{
    ifconfig -s | gawk '{print $1;}' | sed '1d'
}

function get_intf_ip_address
{
    local _intf="$1"    # eg: wlan0

    ifconfig $_intf |\
        grep 'inet addr:' |\
        sed -r 's/[ :]+/ /g' |\
        gawk '{print $3;}'

    #ip -4 addr show $_intf can also be used
}

#----------------------------------------------------------------------------
# MISC. FUNCTIONS

function get_num_digits
{
    #see: https://www.geeksforgeeks.org/given-number-n-decimal-base-find-number-digits-base-base-b/
    #see: https://stackoverflow.com/questions/7962283/how-do-i-calculate-the-log-of-a-number-using-bc
    #see: https://stackoverflow.com/questions/20558710/bc-truncate-floating-point-number

    local _n=$1
    local _base=$2

cat <<EOD | bc -l
x=(l($_n)/l($_base))+1
scale=0
x/1
EOD
}

function to_lower
{
    #see: https://stackoverflow.com/questions/2264428/how-to-convert-a-string-to-lower-case-in-bash
    local _in="$1"
    echo ${_in,,}
}

function get_num_fields
{
    local _str="$1"
    local _fs="$2"

    local _n=`echo "$_str" |\
              gawk -F "$_fs" '{ n = split($0, arr, FS); print n; }'`

    echo "$_n"
}

function remove_comments
{
    grep -v -e '^[ \t]*#'
}

function echo_var_name_value
{
    local _var_name="$1"

    eval "echo $_var_name=\$$_var_name"
}

function get_last_line_number
{
    local _filepath="$1"

    wc -l $_filepath | gawk '{print $1;}'
}

function cat_file_with_env_vars
{
    local _filepath="$1"
    local _tmp="$2"

    echo "cat <<EOD" > $_tmp
    cat $_filepath >> $_tmp
    echo "EOD" >> $_tmp

    source $_tmp
}

function normalize_file
{
    # stdin --(normalize_file)--> stdout

    sed 's/[ \t]*//g' | sort | uniq
}

function install_packages
{
    local _packages_filepath="$1"
    local _tmp1=`get_tmp_file`

    echo "0" > $_tmp1

    cat $_packages_filepath |\
    while read package_name
    do
        if ! sudo apt-get install $package_name
        then
            echo "unable to install package $package_name" >&2
            echo "1" > $_tmp1
            break
        fi
    done

    local _ret=`cat $_tmp1`
    release_tmp_file $_tmp1

    return $_ret
}

function set_sudo_password
{
    #TODO: use with great caution
    #-v stays sticky for some time and can cause havoc.

    local _sudopswd="$1"
    sudo -v -S <<< "$_sudopswd"
}

function compute_md5sum
{
    local _in_filepath="$1"
    local _md5sum=""
    local _filename=""

    read _md5sum _filename <<< "`md5sum $_in_filepath`"
    echo "$_md5sum"
}

function countdown_sleep
{
    local _interval=$1

    while ((_interval > 0))
    do
        printf "%05d\r" $_interval
        ((_interval = _interval - 1))
    done
    printf "\n"
}
