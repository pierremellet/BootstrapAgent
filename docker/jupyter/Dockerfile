FROM quay.io/jupyter/minimal-notebook

RUN pip install jupyter_kernel_gateway pandas matplotlib sympy

EXPOSE 8888

WORKDIR /app

CMD ["jupyter", "kernelgateway", "--KernelGatewayApp.seed_uri='/notebooks/root.ipynb'","--JupyterWebsocketPersonality.list_kernels=True", "--KernelGatewayApp.ip=0.0.0.0", "--KernelGatewayApp.port=8888"]
