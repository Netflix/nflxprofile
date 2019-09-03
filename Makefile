all: python/nflxprofile/nflxprofile_pb2.py

python/nflxprofile/nflxprofile_pb2.py: nflxprofile.proto
	@protoc --python_out=python/nflxprofile nflxprofile.proto
