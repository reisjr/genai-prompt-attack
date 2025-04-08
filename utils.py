import boto3
import os
import json
import botocore.config
from dotenv import load_dotenv

# loading environment variables
load_dotenv()

DEFAULT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
REGION = "us-east-1"

# MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
# MODEL_ID = "meta.llama3-1-405b-instruct-v1:0" # Different prompt format
# MODEL_ID = "meta.llama3-1-70b-instruct-v1:0"


# configure Bedrock client
def get_bedrock_cli(config):
    region = config.get("region", "us-east-1")

    boto3.setup_default_session(profile_name=os.getenv("profile_name"))
    config = botocore.config.Config(connect_timeout=120, read_timeout=120)
    bedrock = boto3.client('bedrock-runtime', region, endpoint_url=f'https://bedrock-runtime.{region}.amazonaws.com',
                        config=config)

    print(f"Bedrock client: {region}")

    return bedrock


def get_model_id(config):
    model_name = config.get("model", None)
    model_id = DEFAULT_MODEL_ID
    
    if model_name == "Claude 3.5":
        model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    elif model_name == "Claude 3.5 v2":
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    elif model_name == "Llama 3.2 90B":
        model_id = "us.meta.llama3-2-90b-instruct-v1:0"
    elif model_name == "Mistral Large 2402":
        model_id = "mistral.mistral-large-2402-v1:0"
    elif model_name == "Command R+":
        model_id = "cohere.command-r-v1:0"
    
    return model_id


def invoke_llm(user_input, config_rev, config) -> str:
    bedrock_cli = get_bedrock_cli(config)

    print("user_input", user_input)

    initial_message = [{
        "role": "user",
        "content": [{ 
            "text": user_input 
        }]
    }]
    
    inference_config = {
        "maxTokens": 1024,
        "temperature": 0.5,
        "topP": 0.9
    }

    model_id = get_model_id(config)

    response = bedrock_cli.converse(
        modelId=model_id,
        messages=initial_message,
        # system=[
        #   { "text": "" }
        # ],
        inferenceConfig=inference_config,
        # additionalModelRequestFields=additional_model_fields
    )

    # getting the response from Claude3 and parsing it to return to the end user
    print(response)
    
    # {'ResponseMetadata': {'RequestId': 'a7a7feaf-2b5b-4f89-aba5-053391fe8fc9', 'HTTPStatusCode': 200, 'HTTPHeaders': {'date': 'Sat, 30 Nov 2024 21:02:18 GMT', 'content-type': 'application/json', 'content-length': '269', 'connection': 'keep-alive', 'x-amzn-requestid': 'a7a7feaf-2b5b-4f89-aba5-053391fe8fc9'}, 'RetryAttempts': 0}, 'output': {'message': {'role': 'assistant', 'content': [{'text': 'Sinto muito, mas não posso ajudar com atividades ilegais como invasão de residências.'}]}}, 'stopReason': 'end_turn', 'usage': {'inputTokens': 22, 'outputTokens': 30, 'totalTokens': 52}, 'metrics': {'latencyMs': 905}}
    
    # response_body = json.loads(response.get('body').read())
    # # the final string returned to the end user
    answer = response.get("output").get("message").get("content")[0].get("text")
    
    # latency = 0
    # input_tokens = 0
    # output_tokens = 0

    if "ResponseMetadata" in response:
        resp_headers = response.get("ResponseMetadata").get("HTTPHeaders")
        latency = resp_headers.get("x-amzn-bedrock-invocation-latency")
        input_tokens = resp_headers.get("x-amzn-bedrock-input-token-count")
        output_tokens = resp_headers.get("x-amzn-bedrock-output-token-count")

        # print(f"Model: {model_id} Latency: {latency:4} in tokens: {input_tokens:4} out tokens: {output_tokens:4}")


    # returning the final string to the end user
    return answer, latency, input_tokens, output_tokens, config.get("model", None)


def invoke_llm_refine(bedrock, user_feedback, previous_version, doc_template, config) -> str:
    # Setup Prompt - This prompt passes in the document template and the user feedback, and the previous version to generate the refined draft of the
    # document the user is looking to create.
    prompt_data = f"""

Human:

I want you to act as a proofreader and writer. I'll provide you with an extract.

Proofread for grammatical errors and ensure it is written clearly.
Phrases that can be written more clearly should be done so. Write the extract with the relevant changes and share a list of improvements made.

###
<document_to_be_refined>
{previous_version}
</document_to_be_refined>

<User_feedback>
{user_feedback}
</User_feedback>

<Document_Template>
{doc_template}
</Document_Template>
###

Assistant: Here is a modified draft press release based on the provided user feedback

"""
    # Add the prompt to the body to be passed to the Bedrock API along with parameters
    prompt = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 10000,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_data
                    }
                ]
            }
        ]
    }

    model_id = get_model_id(config)

    # formatting the prompt as a json string
    json_prompt = json.dumps(prompt)
    # invoking Claude3, passing in our prompt
    response = bedrock.invoke_model(body=json_prompt, modelId=model_id,
                                    accept="application/json", contentType="application/json")
    # getting the response from Claude3 and parsing it to return to the end user
    response_body = json.loads(response.get('body').read())
    # the final string returned to the end user
    answer = response_body['content'][0]['text']
    # returning the final string to the end user
    return answer

def translate_text(user_input, lang, config) -> str:
    prompt_data = f"""

Human:

I want you to act as an experienced translator. I'll provide you with an text in <User_Input>.
Translate the text to {lang}.
###

<User_Input>
{user_input}
</User_Input>
###

Assistant: Here is a draft based on the provided user input and template

"""
    # Add the prompt to the body to be passed to the Bedrock API along with parameters
    prompt = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 10000,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_data
                    }
                ]
            }
        ]
    }
    model_id = get_model_id(config)
    bedrock = get_bedrock_cli(config)

    # formatting the prompt as a json string
    json_prompt = json.dumps(prompt)
    # invoking Claude3, passing in our prompt
    response = bedrock.invoke_model(body=json_prompt, modelId=model_id,
                                    accept="application/json", contentType="application/json")
    # print(response)

    # getting the response from Claude3 and parsing it to return to the end user
    response_body = json.loads(response.get('body').read())
    # the final string returned to the end user
    answer = response_body['content'][0]['text']
    
    # print(response)
    # print(response.get("ResponseMetadata"))
    # print(response.get("ResponseMetadata").get("HTTPHeaders"))
    # print(response_body)
    
    if "ResponseMetadata" in response:
        resp_headers = response.get("ResponseMetadata").get("HTTPHeaders")
        latency = resp_headers.get("x-amzn-bedrock-invocation-latency")
        input_tokens = resp_headers.get("x-amzn-bedrock-input-token-count")
        output_tokens = resp_headers.get("x-amzn-bedrock-output-token-count")

        print(f"Model: {model_id} Latency: {latency:4} in tokens: {input_tokens:4} out tokens: {output_tokens:4}")

    # returning the final string to the end user
    return answer


def run_open_request(user_prompt, user_data, config) -> str:
    bedrock = get_bedrock_cli(config)

    llmOutput = invoke_llm(bedrock, user_prompt, user_data, config)
    text_reviewed_scaped = llmOutput[0].replace(":", "\:")
    
    print("reviewed")
    print(text_reviewed_scaped)

    return text_reviewed_scaped, llmOutput[1], llmOutput[2], llmOutput[3]

