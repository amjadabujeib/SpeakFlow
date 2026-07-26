FROM kaldiasr/kaldi:latest

RUN apt-get update && apt-get install -y wget unzip python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages numpy pandas

WORKDIR /opt/kaldi/egs

# Setup the speechocean762 env
RUN cp -r gop_speechocean762/s5 gop_inference
WORKDIR /opt/kaldi/egs/gop_inference

# Download the m13 acoustic models for LibriSpeech
RUN mkdir -p /opt/kaldi/egs/librispeech/s5 && cd /opt/kaldi/egs/librispeech/s5 && \
    wget https://kaldi-asr.org/models/13/0013_librispeech_v1_chain.tar.gz && \
    wget https://kaldi-asr.org/models/13/0013_librispeech_v1_extractor.tar.gz && \
    wget https://kaldi-asr.org/models/13/0013_librispeech_v1_lm.tar.gz && \
    tar -xzf 0013_librispeech_v1_chain.tar.gz && \
    tar -xzf 0013_librispeech_v1_extractor.tar.gz && \
    tar -xzf 0013_librispeech_v1_lm.tar.gz && \
    rm *.tar.gz

# Modify run.sh to point to the models
RUN sed -i 's|librispeech_eg=.*|librispeech_eg=../../librispeech/s5|' run.sh && \
    sed -i 's|model=$librispeech_eg/exp/chain_cleaned/tdnn_1d_sp|model=$librispeech_eg/exp/chain/tdnn_1d_sp|' run.sh

# We will inject the test data using a shared volume at runtime.

COPY extract_gop.sh /usr/local/bin/english-tutor-extract-gop
RUN chmod 0755 /usr/local/bin/english-tutor-extract-gop
