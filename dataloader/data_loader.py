from PIL import Image, ImageFile
import torchvision.transforms as transforms
import torch.utils.data as data
from .image_folder import make_dataset
from util import task
import random


class CreateDataset(data.Dataset):
    def __init__(self, opt):
        self.opt = opt
        self.img_paths, self.img_size = make_dataset(opt.img_file)
        self.img_feature_paths, self.img_feature_size = make_dataset(opt.img_feature_file)
        # provides random file for training and testing
        if opt.mask_file != 'none':
            self.mask_paths, self.mask_size = make_dataset(opt.mask_file)
        self.transform = get_transform(opt)

    def __getitem__(self, index):
        # load image
        img, img_path = self.load_img(index)
        # load mask
        mask = self.load_mask(img, index)
        # load feature image
        img_feature, img_feature_path = self.load_img_feature(index)
        return {'img': img, 'img_path': img_path, 'mask': mask, 'img_feature': img_feature, 'img_feature_path': img_feature_path}

    def __len__(self):
        return self.img_size

    def name(self):
        return "inpainting dataset"

    def load_img(self, index):
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        img_path = self.img_paths[index % self.img_size]
        img_pil = Image.open(img_path).convert('RGB')
        img = self.transform(img_pil)
        img_pil.close()
        return img, img_path

    def load_img_feature(self, index):
        if self.opt.pretrain:
            random_img = Image.new('RGB', (256, 256))
            pixels = random_img.load()
            for x in range(random_img.size[0]):
                for y in range(random_img.size[1]):
                    pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0,255))
            random_img = self.transform(random_img)
            return random_img, ""
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        img_feature_path = self.img_feature_paths[random.randint(0, self.img_feature_size -1)]
        img_feature_pil = Image.open(img_feature_path).convert('RGB')
        img_feature = self.transform(img_feature_pil)
        img_feature_pil.close()
        return img_feature, img_feature_path

    def load_mask(self, img, index):
        """Load different mask types for training and testing"""
        if self.opt.pretrain:
            mask_type = random.randint(0, 2)
        else:
            mask_type_index = random.randint(0, len(self.opt.mask_type) - 1)
            mask_type = self.opt.mask_type[mask_type_index]

        # center mask
        if mask_type == 0:
            return task.center_mask(img)

        # random regular mask
        if mask_type == 1:
            return task.random_regular_mask(img)

        # random irregular mask
        if mask_type == 2:
            return task.random_irregular_mask(img)

        # external mask from "Image Inpainting for Irregular Holes Using Partial Convolutions (ECCV18)"
        if mask_type == 3:
            if self.opt.isTrain:
                mask_index = random.randint(0, self.mask_size-1)
            else:
                mask_index = index
            mask_pil = Image.open(self.mask_paths[mask_index]).convert('RGB')
            size = mask_pil.size[0]
            if size > mask_pil.size[1]:
                size = mask_pil.size[1]
            mask_transform = transforms.Compose([transforms.RandomHorizontalFlip(),
                                                 transforms.RandomRotation(10),
                                                 transforms.CenterCrop([size, size]),
                                                 transforms.Resize(self.opt.fineSize),
                                                 transforms.ToTensor()
                                                 ])
            mask = (mask_transform(mask_pil) == 0).float()
            mask_pil.close()
            return mask


def dataloader(opt):
    datasets = CreateDataset(opt)
    dataset = data.DataLoader(datasets, batch_size=opt.batchSize, shuffle=not opt.no_shuffle, num_workers=int(opt.nThreads))

    return dataset


def get_transform(opt):
    """Basic process to transform PIL image to torch tensor"""
    transform_list = []
    osize = [opt.loadSize[0], opt.loadSize[1]]
    fsize = [opt.fineSize[0], opt.fineSize[1]]
    if opt.isTrain:
        if opt.resize_or_crop == 'resize_and_crop':
            transform_list.append(transforms.Resize(osize))
            transform_list.append(transforms.RandomCrop(fsize))
        elif opt.resize_or_crop == 'crop':
            transform_list.append(transforms.RandomCrop(fsize))
        if not opt.no_augment:
            transform_list.append(transforms.ColorJitter(0.0, 0.0, 0.0, 0.0))
        if not opt.no_flip:
            transform_list.append(transforms.RandomHorizontalFlip())
        if not opt.no_rotation:
            transform_list.append(transforms.RandomRotation(3))
    else:
        transform_list.append(transforms.Resize(fsize))

    transform_list += [transforms.ToTensor()]

    return transforms.Compose(transform_list)
