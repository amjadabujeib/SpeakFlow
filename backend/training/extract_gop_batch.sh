#!/usr/bin/env bash
set -euo pipefail

training_root=${1:-/training}
nj=${2:-4}
job_dir=${training_root}/kaldi_job
output_dir=${training_root}/kaldi_output
recipe=/opt/kaldi/egs/gop_inference
librispeech=/opt/kaldi/egs/librispeech/s5
model=${librispeech}/exp/chain_cleaned/tdnn_1d_sp
ivector_extractor=${librispeech}/exp/nnet3_cleaned/extractor
lang=${librispeech}/data/lang_test_tgsmall

for required in wav.scp text utt2spk spk2utt lexicon.txt text-phone; do
  test -s "${job_dir}/${required}"
done

mkdir -p "${output_dir}"
cd "${recipe}"
ln -sfn /opt/kaldi/egs/wsj/s5/steps steps
ln -sfn /opt/kaldi/egs/wsj/s5/utils utils
sed -i 's|^export KALDI_ROOT=.*|export KALDI_ROOT=/opt/kaldi|' path.sh
. ./cmd.sh
. ./path.sh

rm -rf data/adaptation data/local/adaptation_dict data/local/adaptation_lang_tmp \
  data/lang_adaptation exp/probs_adaptation exp/ali_adaptation exp/gop_adaptation
mkdir -p data/adaptation data/local exp/ali_adaptation/log exp/gop_adaptation/log
cp "${job_dir}/wav.scp" data/adaptation/wav.scp
cp "${job_dir}/text" data/adaptation/text
cp "${job_dir}/utt2spk" data/adaptation/utt2spk
cp "${job_dir}/spk2utt" data/adaptation/spk2utt
cp "${job_dir}/lexicon.txt" data/local/adaptation_lexicon.txt
cp "${job_dir}/text-phone" data/local/adaptation_text-phone

steps/make_mfcc.sh --nj "${nj}" --mfcc-config conf/mfcc_hires.conf --cmd "${cmd}" data/adaptation
steps/compute_cmvn_stats.sh data/adaptation
utils/fix_data_dir.sh data/adaptation
steps/online/nnet2/extract_ivectors_online.sh \
  --cmd "${cmd}" --nj "${nj}" data/adaptation "${ivector_extractor}" data/adaptation/ivectors
steps/nnet3/compute_output.sh \
  --cmd "${cmd}" --nj "${nj}" --online-ivector-dir data/adaptation/ivectors \
  data/adaptation "${model}" exp/probs_adaptation

local/prepare_dict.sh data/local/adaptation_lexicon.txt data/local/adaptation_dict
utils/prepare_lang.sh --phone-symbol-table "${lang}/phones.txt" \
  data/local/adaptation_dict "<UNK>" data/local/adaptation_lang_tmp data/lang_adaptation

utils/split_data.sh data/adaptation "${nj}"
for index in $(seq 1 "${nj}"); do
  utils/sym2int.pl -f 2- data/lang_adaptation/words.txt \
    "data/adaptation/split${nj}/${index}/text" \
    > "data/adaptation/split${nj}/${index}/text.int"
done
utils/sym2int.pl -f 2- data/lang_adaptation/phones.txt \
  data/local/adaptation_text-phone > data/local/adaptation_text-phone.int

${cmd} JOB=1:"${nj}" exp/ali_adaptation/log/mk_align_graph.JOB.log \
  compile-train-graphs-without-lexicon \
  --read-disambig-syms=data/lang_adaptation/phones/disambig.int \
  "${model}/tree" "${model}/final.mdl" \
  "ark,t:data/adaptation/split${nj}/JOB/text.int" \
  ark,t:data/local/adaptation_text-phone.int \
  "ark:|gzip -c > exp/ali_adaptation/fsts.JOB.gz"
echo "${nj}" > exp/ali_adaptation/num_jobs

steps/align_mapped.sh --cmd "${cmd}" --nj "${nj}" --graphs exp/ali_adaptation \
  data/adaptation exp/probs_adaptation "${lang}" "${model}" exp/ali_adaptation
local/remove_phone_markers.pl "${lang}/phones.txt" \
  data/lang_adaptation/phones-pure.txt data/lang_adaptation/phone-to-pure-phone.int

${cmd} JOB=1:"${nj}" exp/ali_adaptation/log/ali_to_phones.JOB.log \
  ali-to-phones --per-frame=true "${model}/final.mdl" \
  "ark,t:gunzip -c exp/ali_adaptation/ali.JOB.gz|" \
  "ark,t:|gzip -c > exp/ali_adaptation/ali-phone.JOB.gz"

${cmd} JOB=1:"${nj}" exp/gop_adaptation/log/compute_gop.JOB.log \
  compute-gop --phone-map=data/lang_adaptation/phone-to-pure-phone.int \
  --skip-phones-string=0:1:2 "${model}/final.mdl" \
  "ark,t:gunzip -c exp/ali_adaptation/ali.JOB.gz|" \
  "ark,t:gunzip -c exp/ali_adaptation/ali-phone.JOB.gz|" \
  "ark:exp/probs_adaptation/output.JOB.ark" \
  "ark,scp:exp/gop_adaptation/gop.JOB.ark,exp/gop_adaptation/gop.JOB.scp" \
  "ark,scp:exp/gop_adaptation/feat.JOB.ark,exp/gop_adaptation/feat.JOB.scp"

cat exp/gop_adaptation/feat.*.scp | sort > exp/gop_adaptation/feat.scp
copy-vector scp:exp/gop_adaptation/feat.scp "ark,t:${output_dir}/features.txt"
cp data/lang_adaptation/phones-pure.txt "${output_dir}/phones-pure.txt"
cp exp/gop_adaptation/feat.scp "${output_dir}/features.scp"
