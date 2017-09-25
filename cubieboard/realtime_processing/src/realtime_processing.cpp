#include "opencv2/opencv.hpp"
#include "sha256.h"
#include "safequeue.h"

#include <ostream>
#include <fstream>
#include <iostream>
#include <vector>
#include <ctime>
#include <thread>
#include <chrono>

#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>



// #define EVAL

#ifndef EVAL

#define PRINT_DESC
#define PRINT_SRART_VIDEO
#define PRINT_ELAPSED_TIME
#define PRINT_FRAME_COUNT
#define PRINT_FPS
#define PRINT_JOIN
#define PRINT_MEMORY_FREE

#endif



using namespace cv;
using namespace std;
using namespace chrono;



uint8_t * buffer = 0;
struct v4l2_buffer buffer_info = {0};

typedef struct message {
	unsigned char type;
	char* data;
	unsigned int length;
} Message;



const string currentDateTime() {
	time_t now = time(0);
	struct tm tstruct;
	char buf[20];
	tstruct = *localtime(&now);
	strftime(buf, sizeof(buf), "%Y-%m-%d_%X", &tstruct);
	buf[19] = 0;
	return buf;
}


static int xioctl(int fd, int request, void *arg) {
	int r;

	do r = ioctl (fd, request, arg);
	while (-1 == r && EINTR == errno);

	return r;
}


int open_camera(int width, int height) {
	int fd = open("/dev/video0", O_RDWR);
	if (fd == -1) {
		perror("Open video device");
		exit(1);
	}

	struct v4l2_capability cap;
	if (xioctl(fd, VIDIOC_QUERYCAP, &cap) < 0) {
		perror("VIDIOC_QUERYCAP");
		exit(1);
	}

	struct v4l2_format fmt;
	memset(&fmt, 0, sizeof(struct v4l2_format));

	fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	fmt.fmt.pix.width = width;
	fmt.fmt.pix.height = height;
	fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
	fmt.fmt.pix.field = V4L2_FIELD_NONE;

	if (-1 == xioctl(fd, VIDIOC_S_FMT, &fmt))
	{
		perror("VIDIOC_S_FMT");
		exit(1);
	}

	struct v4l2_requestbuffers bufrequest;
	memset(&bufrequest, 0, sizeof(struct v4l2_requestbuffers));

	bufrequest.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	bufrequest.memory = V4L2_MEMORY_MMAP;
	bufrequest.count = 1;

	if(ioctl(fd, VIDIOC_REQBUFS, &bufrequest) < 0){
		perror("VIDIOC_REQBUFS");
		exit(1);
	}

	memset(&buffer_info, 0, sizeof(struct v4l2_buffer));

	buffer_info.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	buffer_info.memory = V4L2_MEMORY_MMAP;
	buffer_info.index = 0;
	if(-1 == xioctl(fd, VIDIOC_QUERYBUF, &buffer_info))
	{
		perror("VIDIOC_QUERYBUF");
		exit(1);
	}

	buffer = (uint8_t *) mmap (NULL, buffer_info.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buffer_info.m.offset);
	memset(buffer, 0, buffer_info.length);

	if(-1 == xioctl(fd, VIDIOC_STREAMON, &buffer_info.type))
	{
		perror("VIDIOC_STREAMON");
		exit(1);
	}

	return fd;
}


int close_camera(int fd) {
	if (-1 == xioctl(fd, VIDIOC_STREAMOFF, &buffer_info.type)) {
		perror("VIDIOC_STREAMOFF");
		exit(1);
	}

	return close(fd);
}


void get_frame(int fd) {
	if (-1 == xioctl(fd, VIDIOC_QBUF, &buffer_info))
	{
		perror("VIDIOC_QBUF");
		exit(1);
	}

	fd_set fds;
	FD_ZERO(&fds);
	FD_SET(fd, &fds);
	struct timeval tv = {0};
	tv.tv_sec = 2;
	if(-1 == select(fd+1, &fds, NULL, NULL, &tv))
	{
		perror("Waiting for Frame");
		exit(1);
	}

	if(-1 == xioctl(fd, VIDIOC_DQBUF, &buffer_info))
	{
		perror("VIDIOC_DQBUF");
		exit(1);
	}
}



void func_realtime(SafeQueue<Message *> &sq) {
	// open ved file
	ofstream ved;
	ved.rdbuf()->pubsetbuf(0, 0);

	Message * m = 0;

	while (1) {
		m = sq.dequeue();
		if (m == 0) { continue; }
		else if (m->type == 0) { /* start video */ string name = m->data; ved.open("../data/video/" + name + ".ved", ios::out | ios::binary); free(m->data); free(m); continue; }
		else if (m->type == 1) { /* frame       */ }
		else if (m->type == 2) { /* end video   */ free(m); break; }

		// write ved file
		for (int i = 0; i < 4; i++) { ved << ((uchar *) &(m->length))[3 - i]; }
		ved.write((char *) m->data, m->length);

		free(m->data);
		free(m);
	}

	// close ved file
	ved.close();
}



int main(int argc, char * argv[], char * envp[]) {
	if (argc != 5) {
		cout << argv[0] << " (time) (row) (column) (scale)" << endl;
		exit(1);
	}

	int time = 0, row = 0, col = 0;
	double scale = 0.0, f = 0.0;

	istringstream ss_time(argv[1]);
	if (!(ss_time >> time)) { cout << "arg: time" << endl; return 1; }
	istringstream ss_row(argv[2]);
	if (!(ss_row >> row)) { cout << "arg: row" << endl; return 1; }
	istringstream ss_col(argv[3]);
	if (!(ss_col >> col)) { cout << "arg: col" << endl; return 1; }
	istringstream ss_scale(argv[4]);
	if (!(ss_scale >> scale)) { cout << "arg: scale" << endl; return 1; }

	time = strtol(argv[1], 0, 10);
	row = strtol(argv[2], 0, 10);
	col = strtol(argv[3], 0, 10);
	scale = strtod(argv[4], 0);
	f = 1.0 / scale;

#ifdef PRINT_DESC
	cout << "capture" << endl;
	cout << "  video time  : " << time << endl;
	cout << "  block row   : " << row << endl;
	cout << "        column: " << col << endl;
	cout << "        scale : " << scale << endl;
#endif

	int fd = open_camera(640, 480);

	for (int loop = 5; loop > 0; loop--) {
		SHA256 ctx = SHA256();
		unsigned char * digest = (unsigned char *) malloc(32);

		string now = currentDateTime();

#ifdef PRINT_START_VIDEO
		cout << "record " << now << ".ved" << endl;
#endif

		// send message : start video
		SafeQueue<Message*> sq;
		{
			Message * m = (Message *) malloc(sizeof(Message));
			m->type = 0;
			m->data = (char *) malloc(20); copy(now.begin(), now.end(), m->data); m->data[19] = '\0';
			m->length = 20;
			sq.enqueue(m);
		}

		thread thread_realtime(&func_realtime, ref(sq));

		int count = 0;
		auto t_start = chrono::high_resolution_clock::now(), t_current = t_start;
		auto t_exit = t_start + duration<int>(time);
		// auto t_process = t_start + duration<int, milli>(50);
		while (1) {
			t_current = chrono::high_resolution_clock::now();
			if (t_current >= t_exit) { break; }

			//if (t_current < t_process) { continue; }
			//t_process += chrono::duration<int, milli>(50);

			// get encoded frame
			get_frame(fd);

			// get length of encoded frame
			int len = 0;
			for (len = buffer_info.length/3 - 1;len >= 0 && buffer[len] == 0; len--); len++;
			if (len == 0) { continue; }

			// send message : video frame
			{
				Message * m = (Message *) malloc(sizeof(Message));
				m->type = 1;
				m->data = (char *) malloc(sizeof(char) * len); memcpy(m->data, buffer, len);
				m->length = len;
				sq.enqueue(m);
			}

			// hash frame data
			Mat frame, shrink;
			Mat raw(1, len, CV_8UC1, buffer);

			frame = imdecode(raw, CV_LOAD_IMAGE_COLOR); // 0.024 ~ 0.038
			cvtColor(frame, frame, CV_BGR2RGB);

			int width = frame.cols, height = frame.rows; // 0.004394 ~ 0.014670
			for (int r = 0; r < row; r++) {
				for (int c = 0; c < col; c++) {
					int x1 = width * c / col, y1 = height * r / row;
					int x2 = width * (c+1) / col, y2 = height * (r+1) / row;
					resize(frame(Rect(x1, y1, x2-x1, y2-y1)), shrink, Size(), f, f, INTER_NEAREST);
					ctx.update((unsigned char *)shrink.data, shrink.rows * shrink.cols * 3);
				}
			}

			count++;
		}

		chrono::duration<double, milli> fp_ms = chrono::high_resolution_clock::now() - t_start;
#ifdef PRINT_ELAPSED_TIME
		cout << "  elapsed time: " << fp_ms.count() << " ms" << endl;
#endif
#ifdef PRINT_FRAME_COUNT
		cout << "  frame count: " << count << endl;
#endif
#ifdef PRINT_FPS
		cout << "  fps: " << count * 1000 / fp_ms.count() << endl;
#endif

		ctx.final(digest);

		// write vhd file
		ofstream vhd("../data/fingerprint/" + now + ".vhd");
		for (int i = 0; i < 32; i++) { vhd << hex << (int)digest[i]; }
		vhd.close();

		free(digest);

		// send message : end video
		{
			Message * m = (Message *) malloc(sizeof(Message));
			m->type = 2;
			m->data = NULL;
			m->length = 0;
			sq.enqueue(m);
		}

		// write vmd file
		ofstream vmd("../data/meta/" + now + ".vmd");
		vmd << "video_time=" << time << endl;
		vmd << "row=" << row << endl;
		vmd << "column=" << col << endl;
		vmd << "scale=" << scale << endl;
		vmd << "frame_count=" << count << endl;
		vmd.close();

		auto t_join = high_resolution_clock::now();
		thread_realtime.join();
		fp_ms = chrono::high_resolution_clock::now() - t_join;
#ifdef PRINT_JOIN
		cout << "  join: " << fp_ms.count() / 1000 << endl;
#endif

		auto t_memory_free = high_resolution_clock::now();
		system("sudo sh -c 'free > /dev/null && sync && echo 3 > /proc/sys/vm/drop_caches'");
		fp_ms = chrono::high_resolution_clock::now() - t_memory_free;
#ifdef PRINT_MEMORY_FREE
		cout << "  free: " << fp_ms.count() / 1000 << endl;
#endif
	}

	close_camera(fd);

	return 0;
}
