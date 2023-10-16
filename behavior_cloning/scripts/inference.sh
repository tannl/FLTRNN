eval "$(conda shell.bash hook)"
conda activate LID

base_port=8193


for seed in 0; do
for subset in NovelScenes; do

base_port=$((base_port+2))


CUDA_VISIBLE_DEVICES=0 python3 inference.py \
--gpus 1 \
--language_model_type_pretrain 'fine_tune_pretrain' \
--max_episode_length 70 \
--num_mini_batch 1 \
--model_type 'gpt2' \
--model_name_or_path 'gpt2' \
--seed ${seed} \
--base-port ${base_port} \
--eval \
--subset ${subset} \
--test_examples 18 \
--interactive_eval \
--interactive_eval_path interactive_eval/${subset}/seed${seed} \
--pretrained_model_dir checkpoint/LID-Text/model.pt \


done
done
