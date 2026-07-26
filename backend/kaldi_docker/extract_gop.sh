#!/usr/bin/env bash
set -euo pipefail

job_id=${1:?job id is required}
shared_job="/shared/${job_id}"
recipe=/opt/kaldi/egs/gop_inference
librispeech=/opt/kaldi/egs/librispeech/s5
model=${librispeech}/exp/chain_cleaned/tdnn_1d_sp
ivector_extractor=${librispeech}/exp/nnet3_cleaned/extractor
lang=${librispeech}/data/lang_test_tgsmall

for required in wav.scp text utt2spk spk2utt lexicon.txt text-phone; do
  test -s "${shared_job}/${required}"
done
for required in "${model}/final.mdl" "${ivector_extractor}/final.ie" "${lang}/phones.txt"; do
  test -e "${required}"
done

cd "${recipe}"
ln -sfn /opt/kaldi/egs/wsj/s5/steps steps
ln -sfn /opt/kaldi/egs/wsj/s5/utils utils
sed -i 's|^export KALDI_ROOT=.*|export KALDI_ROOT=/opt/kaldi|' path.sh
. ./cmd.sh
. ./path.sh

# The Python caller serializes access to these fixed Kaldi work directories.
rm -rf data/practice data/local/practice_dict data/local/practice_lang_tmp \
  data/lang_practice exp/probs_practice exp/ali_practice exp/gop_practice
mkdir -p data/practice data/local exp/ali_practice/log exp/gop_practice/log
cp "${shared_job}/wav.scp" data/practice/wav.scp
cp "${shared_job}/text" data/practice/text
cp "${shared_job}/utt2spk" data/practice/utt2spk
cp "${shared_job}/spk2utt" data/practice/spk2utt
cp "${shared_job}/lexicon.txt" data/local/practice_lexicon.txt
cp "${shared_job}/text-phone" data/local/practice_text-phone

steps/make_mfcc.sh --nj 1 --mfcc-config conf/mfcc_hires.conf --cmd "${cmd}" data/practice
steps/compute_cmvn_stats.sh data/practice
utils/fix_data_dir.sh data/practice

steps/online/nnet2/extract_ivectors_online.sh \
  --cmd "${cmd}" --nj 1 data/practice "${ivector_extractor}" data/practice/ivectors
steps/nnet3/compute_output.sh \
  --cmd "${cmd}" --nj 1 --online-ivector-dir data/practice/ivectors \
  data/practice "${model}" exp/probs_practice

local/prepare_dict.sh data/local/practice_lexicon.txt data/local/practice_dict
utils/prepare_lang.sh --phone-symbol-table "${lang}/phones.txt" \
  data/local/practice_dict "<UNK>" data/local/practice_lang_tmp data/lang_practice

utils/split_data.sh data/practice 1
utils/sym2int.pl -f 2- data/lang_practice/words.txt \
  data/practice/split1/1/text > data/practice/split1/1/text.int
utils/sym2int.pl -f 2- data/lang_practice/phones.txt \
  data/local/practice_text-phone > data/local/practice_text-phone.int

compile-train-graphs-without-lexicon \
  --read-disambig-syms=data/lang_practice/phones/disambig.int \
  "${model}/tree" "${model}/final.mdl" \
  ark,t:data/practice/split1/1/text.int \
  ark,t:data/local/practice_text-phone.int \
  "ark:|gzip -c > exp/ali_practice/fsts.1.gz"
echo 1 > exp/ali_practice/num_jobs

steps/align_mapped.sh --cmd "${cmd}" --nj 1 --graphs exp/ali_practice \
  data/practice exp/probs_practice "${lang}" "${model}" exp/ali_practice

local/remove_phone_markers.pl "${lang}/phones.txt" \
  data/lang_practice/phones-pure.txt data/lang_practice/phone-to-pure-phone.int
ali-to-phones --per-frame=true "${model}/final.mdl" \
  "ark,t:gunzip -c exp/ali_practice/ali.1.gz|" \
  "ark,t:|gzip -c > exp/ali_practice/ali-phone.1.gz"

compute-gop --phone-map=data/lang_practice/phone-to-pure-phone.int \
  --skip-phones-string=0:1:2 "${model}/final.mdl" \
  "ark,t:gunzip -c exp/ali_practice/ali.1.gz|" \
  "ark,t:gunzip -c exp/ali_practice/ali-phone.1.gz|" \
  ark:exp/probs_practice/output.1.ark \
  ark,scp:exp/gop_practice/gop.1.ark,exp/gop_practice/gop.1.scp \
  ark,scp:exp/gop_practice/feat.1.ark,exp/gop_practice/feat.1.scp

copy-vector scp:exp/gop_practice/feat.1.scp "ark,t:${shared_job}/features.txt"
cp data/lang_practice/phones-pure.txt "${shared_job}/phones-pure.txt"
