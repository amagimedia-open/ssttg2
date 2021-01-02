Streaming speech to text transcription using google apis.
Version 1.0

+-----------------+
| For development |
+-----------------+

(A) To build docker image 

    $ ./build_dev_docker_image.sh

(B) To run unit test cases 

    $ ./ssttg_dev_run_ut_in_docker.sh
    $ tree ./test   # see results here

+-------------+
| For release |
+-------------+

(A) To build docker image 

    $ ./build_rel_docker_image.sh

(B) Have a look-at/try the following

    test/ex/01/run.sh
    test/ex/02/run.sh

