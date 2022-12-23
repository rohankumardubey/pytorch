import torch
from functools import partial
from torch.testing import make_tensor
from torch.testing._internal.opinfo.core import (
    OpInfo,
    SampleInput,
)
from torch.testing._internal.common_dtype import all_types_and
import numpy as np

# Note: [autograd.Function db]
#
# This is a collection of autograd.Function test cases written as OpInfos
# so they can easily be consumed by OpInfo-based tests to check if a subsystem
# supports autograd.Function.
#
# Axes:
# - saves {output, input, intermediate, non-tensor}
# - {inputs, output} x {single tensor, tensors, arbitrary objects}
# - Uses {mark_dirty, mark_non_differentiable, once_differentiable}


def to_numpy(tensor):
    return tensor.cpu().numpy()


class NumpyCube(torch.autograd.Function):
    @staticmethod
    def forward(input):
        input_np = to_numpy(input)
        dinput = torch.tensor(3 * input_np ** 2, device=input.device)
        return torch.tensor(input_np ** 3, device=input.device), dinput

    @staticmethod
    def setup_context(ctx, inputs, output):
        ctx.save_for_backward(inputs[0], output[1])
        ctx.save_for_forward(inputs[0], output[1])

    @staticmethod
    def backward(ctx, grad_output, grad_saved):
        input, dinput = ctx.saved_tensors
        return NumpyMul.apply(grad_output, dinput) + 6 * NumpyMul.apply(grad_saved, input)

    @staticmethod
    def vmap(info, in_dims, input):
        result = NumpyCube.apply(input)
        return result, (in_dims[0], in_dims[0])

    @staticmethod
    def jvp(ctx, input_tangent):
        input, dinput = ctx.saved_tensors
        return NumpyMul.apply(input_tangent, dinput), 6 * NumpyMul.apply(input_tangent, input)

def sample_inputs_numpy_cube(opinfo, device, dtype, requires_grad, **kwargs):
    make_arg = partial(make_tensor, device=device, dtype=dtype, requires_grad=requires_grad)
    yield SampleInput(make_arg(1, low=0.8, high=2), args=())


class NumpyCubeNotComposable(torch.autograd.Function):
    @staticmethod
    def forward(input):
        input_np = to_numpy(input)
        return torch.tensor(input_np ** 3, device=input.device), input_np

    @staticmethod
    def setup_context(ctx, inputs, output):
        _, input_np = output
        ctx.input_np = input_np
        ctx.device = inputs[0].device

    @staticmethod
    @torch.autograd.function.once_differentiable
    def backward(ctx, grad_output, grad_saved):
        result_np = 3 * (ctx.input_np ** 2)
        return torch.tensor(result_np, device=ctx.device)


class NumpyMul(torch.autograd.Function):
    @staticmethod
    def forward(x, y):
        return torch.tensor(to_numpy(x) * to_numpy(y), device=x.device)

    @staticmethod
    def setup_context(ctx, inputs, output):
        ctx.save_for_backward(*inputs)
        ctx.save_for_forward(*inputs)

    @staticmethod
    def backward(ctx, grad_output):
        x, y = ctx.saved_tensors
        gx = None
        if ctx.needs_input_grad[0]:
            gx = NumpyMul.apply(grad_output, y)
        gy = None
        if ctx.needs_input_grad[1]:
            gy = NumpyMul.apply(grad_output, x)
        return gx, gy

    @staticmethod
    def vmap(info, in_dims, x, y):
        x_bdim, y_bdim = in_dims
        x = x.movedim(x_bdim, -1) if x_bdim is not None else x.unsqueeze(-1)
        y = y.movedim(y_bdim, -1) if y_bdim is not None else y.unsqueeze(-1)
        result = NumpyMul.apply(x, y)
        result = result.movedim(-1, 0)
        return result, 0

    @staticmethod
    def jvp(ctx, x_tangent, y_tangent):
        x, y = ctx.saved_tensors
        return x_tangent * y + y_tangent * x

def sample_inputs_numpy_mul(opinfo, device, dtype, requires_grad, **kwargs):
    make_arg = partial(make_tensor, device=device, dtype=dtype, requires_grad=requires_grad)
    # Broadcasting
    yield SampleInput(make_arg(4, low=0.9, high=2), args=(make_arg(3, 4, low=0.9, high=2),))


class NumpyExp_(torch.autograd.Function):
    @staticmethod
    def forward(x):
        x_np = to_numpy(x)
        np.exp(x_np, x_np)
        return x

    @staticmethod
    def setup_context(ctx, inputs, output):
        x, = inputs
        ctx.mark_dirty(x)
        ctx.save_for_backward(output)
        ctx.save_for_forward(output)

    @staticmethod
    def backward(ctx, grad_output):
        output, = ctx.saved_tensors
        return NumpyMul.apply(grad_output, output)

    @staticmethod
    def vmap(info, in_dims, x):
        NumpyExp_.apply(x)
        return x, in_dims[0]

    @staticmethod
    def jvp(ctx, x_tangent):
        # Doesn't call numpy operations because I didn't want to write NumpyMul_
        output, = ctx.saved_tensors
        x_tangent.mul_(output)
        return x_tangent

class NumpySort(torch.autograd.Function):
    @staticmethod
    def forward(x, dim):
        device = x.device
        x = to_numpy(x)
        ind = np.argsort(x, axis=dim)
        ind_inv = np.argsort(ind, axis=dim)
        result = np.take_along_axis(x, ind, axis=dim)
        return (
            torch.tensor(x, device=device),
            torch.tensor(ind, device=device),
            torch.tensor(ind_inv, device=device),
        )

    @staticmethod
    def setup_context(ctx, inputs, output):
        x, dim = inputs
        _, ind, ind_inv = output
        ctx.mark_non_differentiable(ind, ind_inv)
        ctx.save_for_backward(ind, ind_inv)
        ctx.save_for_forward(ind, ind_inv)
        ctx.dim = dim

    @staticmethod
    def backward(ctx, grad_output, _0, _1):
        ind, ind_inv = ctx.saved_tensors
        return NumpyTake.apply(grad_output, ind_inv, ind, ctx.dim), None

    @staticmethod
    def vmap(info, in_dims, x, dim):
        x_bdim, _ = in_dims
        x = x.movedim(x_bdim, 0)
        # wrap dim
        dim = dim if dim >= 0 else dim + x.dim() - 1
        return NumpySort.apply(x, dim + 1), (0, 0, 0)

    @staticmethod
    def jvp(ctx, x_tangent, _):
        ind, ind_inv = ctx.saved_tensors
        return NumpyTake.apply(x_tangent, ind, ind_inv, ctx.dim), None, None

def sample_inputs_numpy_sort(opinfo, device, dtype, requires_grad, **kwargs):
    make_arg = partial(make_tensor, device=device, dtype=dtype, requires_grad=requires_grad)
    yield SampleInput(make_arg(3, 5), args=(1,))


class NumpyTake(torch.autograd.Function):
    @staticmethod
    def forward(x, ind, ind_inv, dim):
        device = x.device
        x = to_numpy(x)
        ind = to_numpy(ind)
        return torch.tensor(np.take_along_axis(x, ind, dim), device=device)

    @staticmethod
    def setup_context(ctx, inputs, output):
        x, ind, ind_inv, dim = inputs
        ctx.save_for_backward(ind, ind_inv)
        ctx.save_for_forward(ind, ind_inv)
        ctx.dim = dim

    @staticmethod
    def backward(ctx, grad_output):
        ind, ind_inv = ctx.saved_tensors
        result = NumpyTake.apply(grad_output, ind_inv, ind, ctx.dim)
        return result, None, None, None

    @staticmethod
    def vmap(info, in_dims, x, ind, ind_inv, dim):
        x_bdim, ind_bdim, ind_inv_bdim, _ = in_dims

        # wrap dim
        logical_dim = x.dim() if x_bdim is None else x_bdim - 1
        dim = dim if dim >= 0 else dim + logical_dim

        def expand_bdim(x, x_bdim):
            if x_bdim is None:
                return x.expand(info.batch_size, *x.shape)
            return x.movedim(x_bdim, 0)

        x = expand_bdim(x, x_bdim)
        ind = expand_bdim(ind, ind_bdim)
        ind_inv = expand_bdim(ind_inv, ind_inv_bdim)

        return NumpyTake.apply(x, ind, ind_inv, dim + 1), 0

    @staticmethod
    def jvp(ctx, x_tangent, ind_tangent, ind_inv_tangent, _):
        assert ind_tangent is None
        assert ind_inv_tangent is None
        ind, ind_inv = ctx.saved_tensors
        return NumpyTake.apply(x_tangent, ind, ind_inv, ctx.dim)

class Select(torch.autograd.Function):
    @staticmethod
    def forward(x, idx):
        return x[idx]

    @staticmethod
    def setup_context(ctx, inputs, output):
        x, idx = inputs
        ctx.x_shape = x.shape
        ctx.idx = idx

    @staticmethod
    def backward(ctx, grad_output):
        result = grad_output.new_zeros(ctx.x_shape)
        result[ctx.idx] = grad_output
        return result, None

    @staticmethod
    def vmap(info, in_dims, x, idx):
        x_bdim, _ = in_dims
        x = x.movedim(x_bdim, 1)
        return Select.apply(x, idx), 0

    @staticmethod
    def jvp(ctx, x_tangent, _):
        return Select.apply(x_tangent, ctx.idx)


def sample_inputs_select(opinfo, device, dtype, requires_grad, **kwargs):
    make_arg = partial(make_tensor, device=device, dtype=dtype, requires_grad=requires_grad)
    yield SampleInput(make_arg(3, 5), args=(2,))


autograd_function_db = [
    OpInfo(
        'NumpyCubeAutogradFunction',
        op=NumpyCube.apply,
        supports_forward_ad=True,
        supports_fwgrad_bwgrad=True,
        sample_inputs_func=sample_inputs_numpy_cube,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
    ),
    OpInfo(
        'NumpyExpMarkDirtyAutogradFunction',
        op=lambda x: NumpyExp_.apply(x.clone()),
        inplace_variant=NumpyExp_.apply,
        supports_forward_ad=True,
        supports_fwgrad_bwgrad=True,
        sample_inputs_func=sample_inputs_numpy_cube,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
    ),
    OpInfo(
        'NumpyMulAutogradFunction',
        op=NumpyMul.apply,
        supports_forward_ad=True,
        supports_fwgrad_bwgrad=True,
        sample_inputs_func=sample_inputs_numpy_mul,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
    ),
    OpInfo(
        'NumpyCubeNotComposableAutogradFunction',
        op=lambda x: NumpyCubeNotComposable.apply(x)[0],
        supports_forward_ad=False,
        supports_fwgrad_bwgrad=False,
        sample_inputs_func=sample_inputs_numpy_cube,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
    ),
    OpInfo(
        'NumpySortAutogradFunction',
        op=NumpySort.apply,
        supports_forward_ad=False,
        supports_fwgrad_bwgrad=False,
        sample_inputs_func=sample_inputs_numpy_sort,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
        gradcheck_wrapper=lambda y, ind: y,
    ),
    OpInfo(
        'SelectAutogradFunction',
        op=Select.apply,
        supports_forward_ad=True,
        supports_fwgrad_bwgrad=True,
        sample_inputs_func=sample_inputs_select,
        dtypes=all_types_and(torch.bool, torch.half),
        supports_out=False,
    ),
]
