import logging
import torch

from mmcv.cnn import constant_init, kaiming_init
from mmcv.runner import load_checkpoint
from models.backbone.baseblock import *
from models.backbone.helper import load_mobilev2
class MobileNetV2(nn.Module):
    def __init__(self,
                 pretrained=None,
                 out_indices=(6, 13, 18),
                 width_mult=1.,
                 ):
        super(MobileNetV2, self).__init__()
        self.backbone_outchannels=[1280,96,32]
        block = InvertedResidual
        input_channel = 32
        last_channel = 1280
        interverted_residual_setting = [
            # t, c, n, s
            [1, 16, 1, 1],
            [6, 24, 2, 2],
            [6, 32, 3, 2],
            [6, 64, 4, 2],
            [6, 96, 3, 1],
            [6, 160, 3, 2],
            [6, 320, 1, 1],
        ]

        input_channel = int(input_channel * width_mult)
        # 1280
        self.out_indices = out_indices
        # self.zero_init_residual = zero_init_residual
        self.last_channel = int(last_channel * width_mult) if width_mult > 1.0 else last_channel

        self.features = [conv_bn(3, input_channel, 3,2,1)]
        # building inverted residual blocks
        for t, c, n, s in interverted_residual_setting:
            output_channel = int(c * width_mult)
            for i in range(n):
                if i == 0:
                    self.features.append(block(input_channel, output_channel, s, expand_ratio=t))
                else:
                    self.features.append(block(input_channel, output_channel, 1, expand_ratio=t))
                input_channel = output_channel
        self.features.append(conv_bn(input_channel,self.last_channel, 1,1,0))
        self.features = nn.Sequential(*self.features)
        if pretrained:
            load_mobilev2(self,pretrained)
    def init_weights(self, pretrained=None):
        if isinstance(pretrained, str):
            logger = logging.getLogger()
            load_checkpoint(self, pretrained, strict=False, logger=logger)
        elif pretrained is None:
            for m in self.modules():
                if isinstance(m, nn.Conv2d):
                    kaiming_init(m)
                elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                    constant_init(m, 1)
        else:
            raise TypeError('pretrained must be a str or None')

    def forward(self, x):
        outs = []
        for i in range(len(self.features)):
            x = self.features[i](x)
            if i in self.out_indices:
                outs.append(x)
        return outs

if __name__ == '__main__':
    from thop import profile,clever_format
    net=MobileNetV2()
    input=torch.ones(1,3,320,320)
    flops, params = profile(net, inputs=(input,), verbose=False)
    flops, params = clever_format([flops, params], "%.3f")
    print(flops,params)
    assert 0
    net=net.eval()
    with open('mobilev2.pkl', 'rb') as f:
        weights = pickle.load(f, encoding='latin1')
    img=img_preprocess2(cv2.imread('cat.jpg'),None,(320,320),False,False)
    # for idx,(k,v) in enumerate(net.state_dict().items()):
    #     print(idx,k,v.shape)
    # assert 0
    statedict=net.state_dict()
    for k,v in net.state_dict().items():
        if 'num_batches_tracked' in k:
            statedict.pop(k)
    newstatedict=OrderedDict()
    for idx,((k,v),(k2,v2)) in enumerate(zip(statedict.items(),weights.items())):
        print(k,'->',k2.strip('YoloV3/MobilenetV2'))
        if v.ndim>1:
            if 'depthwise' in k2:
                newstatedict.update({k:torch.from_numpy(v2.transpose(2,3,0,1))})
            else:
                newstatedict.update({k:torch.from_numpy(v2.transpose(3,2,0,1))})
        else:
            newstatedict.update({k:torch.from_numpy(v2)})
    input=torch.from_numpy(img.transpose(2,0,1)).unsqueeze(0)
    net.load_state_dict(newstatedict)
    torch.save(net.state_dict(),'mobilev2_tf.pth')
    output=net(input)
    for o in output:
        print(o.shape)
    # print(net)